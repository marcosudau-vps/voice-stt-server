"""One bounded, volatile download queue shared by all STT engines.

Callbacks delegate product rights, installation and events to their existing
authorities. No network, settings persistence or engine imports live here.
"""
from collections import OrderedDict
from datetime import datetime, timezone
import threading
import uuid


TERMINAL = frozenset({"completed", "failed", "cancelled"})
NEXT = {"downloading": "verifying", "verifying": "installing"}


class ModelManagementError(RuntimeError):
    def __init__(self, code, status=409):
        self.code = code
        self.status = status
        super().__init__(code)


def _now():
    return datetime.now(timezone.utc).isoformat()


class DownloadJobManager:
    def __init__(self, *, gate, installed, install, completed, emit=None, limit=128):
        self._gate = gate
        self._installed = installed
        self._install = install
        self._completed = completed
        self._emit = emit or (lambda event, **data: None)
        self._limit = max(1, int(limit))
        self._jobs = OrderedDict()
        self._condition = threading.Condition(threading.RLock())
        self._stopping = False
        self._thread = None

    def start(self):
        with self._condition:
            if self._thread is not None:
                return
            self._thread = threading.Thread(target=self._run, name="STTDownloads", daemon=True)
            self._thread.start()

    def stop(self, timeout=5):
        # A process shutdown may interrupt a transfer. Never claim cancellation
        # of a started job or persist it for an implicit retry.
        with self._condition:
            self._stopping = True
            self._condition.notify_all()
            thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout)

    @staticmethod
    def _public(job):
        return {**job, "origins": sorted(job["origins"])}

    def _prune(self):
        while len(self._jobs) >= self._limit:
            oldest = next((key for key, job in self._jobs.items() if job["state"] in TERMINAL), None)
            if oldest is None:
                raise ModelManagementError("download_queue_full")
            del self._jobs[oldest]

    def enqueue(self, model_id, origin="manual"):
        if origin not in {"manual", "automatic"}:
            raise ValueError("invalid download origin")
        # Authorization is a transport responsibility. Product gates run before
        # even creating a job and again at execution/installation boundaries.
        product = self._gate(model_id)
        with self._condition:
            if self._stopping:
                raise ModelManagementError("download_manager_stopping")
            for job in self._jobs.values():
                if job["modelId"] == model_id and job["state"] not in TERMINAL:
                    job["origins"].add(origin)
                    return self._public(job), False
            if self._installed(product):
                return {"modelId": model_id, "alreadyInstalled": True, "jobId": None}, False
            self._prune()
            job = {
                "jobId": str(uuid.uuid4()), "modelId": model_id, "engine": product.engine,
                "state": "queued", "origins": {origin}, "createdAt": _now(),
                "startedAt": None, "finishedAt": None, "downloadedBytes": 0,
                "totalBytes": product.bytes, "percent": 0.0 if product.bytes else None,
                "errorCode": None,
            }
            self._jobs[job["jobId"]] = job
            self._event("queued", job)
            self._condition.notify_all()
            return self._public(job), True

    def _event(self, event, job):
        self._emit("stt.download." + event, jobId=job["jobId"],
                   modelId=job["modelId"], engine=job["engine"], errorCode=job["errorCode"])

    def snapshot(self, job_id=None):
        with self._condition:
            if job_id is None:
                return [self._public(job) for job in self._jobs.values()]
            if job_id not in self._jobs:
                raise ModelManagementError("download_not_found", 404)
            return self._public(self._jobs[job_id])

    def references(self, model_id):
        with self._condition:
            return any(job["modelId"] == model_id and job["state"] not in TERMINAL
                       for job in self._jobs.values())

    def cancel(self, job_id):
        with self._condition:
            if job_id not in self._jobs:
                raise ModelManagementError("download_not_found", 404)
            job = self._jobs[job_id]
            if job["state"] != "queued":
                raise ModelManagementError("download_already_started")
            job.update(state="cancelled", finishedAt=_now())
            self._event("cancelled", job)
            return self._public(job)

    def deselect(self, selected):
        selected = set(selected)
        with self._condition:
            for job in self._jobs.values():
                if job["state"] == "queued" and job["modelId"] not in selected:
                    job["origins"].discard("automatic")
                    if not job["origins"]:
                        # Keep the historical origin for an auditable snapshot.
                        job["origins"].add("automatic")
                        job.update(state="cancelled", finishedAt=_now())
                        self._event("cancelled", job)

    def _run(self):
        while True:
            with self._condition:
                self._condition.wait_for(lambda: self._stopping or any(
                    job["state"] == "queued" for job in self._jobs.values()))
                if self._stopping:
                    return
                job = next(job for job in self._jobs.values() if job["state"] == "queued")
                # This transition and cancel share the same linearization lock.
                job.update(state="downloading", startedAt=_now())
                self._event("started", job)

            def transition(state):
                with self._condition:
                    if NEXT.get(job["state"]) != state:
                        raise ModelManagementError("invalid_download_transition", 500)
                    job["state"] = state

            def progress(count):
                with self._condition:
                    total = job["totalBytes"]
                    if count < job["downloadedBytes"] or (total and count > total):
                        raise ModelManagementError("download_size_mismatch", 422)
                    job["downloadedBytes"] = count
                    job["percent"] = round(100 * count / total, 2) if total else None

            try:
                product = self._gate(job["modelId"])
                self._install(product, transition, progress)
                if job["state"] != "installing":
                    raise ModelManagementError("invalid_download_transition", 500)
                self._completed()
                with self._condition:
                    job.update(state="completed", finishedAt=_now())
                    self._event("completed", job)
            except Exception as exc:
                with self._condition:
                    code = exc.code if isinstance(exc, ModelManagementError) else "download_failed"
                    job.update(state="failed", finishedAt=_now(), errorCode=code)
                    self._event("failed", job)
