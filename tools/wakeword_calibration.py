"""Reproducible wake-word score/audio/resource harness (AP-SRV-060).

Three independent measurements, all against the *real* OpenWakeWord backend and
the artifacts this build actually ships:

``artifacts``
    The measured receptive field of every bundled classifier. One embedding
    frame advances the stream by 1280 samples (80 ms at 16 kHz) and the
    embedding model consumes 76 melspectrogram frames (760 ms), so a classifier
    with ``N`` input frames still sees the same utterance for
    ``(N - 1) * 80 + 760`` ms. This is the value the mandatory de-duplication
    window is derived from - it is measured, not chosen.

``resources``
    Init/startup time, RSS before/after, peak RSS and per-chunk detection
    latency for 1, 3 and the maximum selectable number of models.

``scores``
    A full score/chunk trace of one or more WAV files, including every raw
    candidate above the threshold, the accepted detection under the production
    latch rule, duplicate spikes and the resulting wake boundary.

Positive wake-word recordings are *not* part of the repository. Running
``scores`` against negative material characterises false positives only; the
cooldown/pre-roll defaults that depend on real positive speech stay
``EVIDENCE_PENDING`` and are deliberately not simulated.

Usage::

    python tools/wakeword_calibration.py artifacts
    python tools/wakeword_calibration.py resources
    python tools/wakeword_calibration.py scores --audio tests/unit/audio/asr-reference.wav
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
import time
import wave
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from VoiceSTT.core.wake_audio_boundary import resolve_wake_audio_boundary  # noqa: E402
from VoiceSTT.core.wake_detection import (  # noqa: E402
    RawWakeCandidate,
    WakeDetectionEvaluator,
    receptive_field_ms,
    selection_receptive_field_ms,
)
from VoiceSTT.core.wakeword_catalog import WakeWordCatalogAuthority  # noqa: E402


SAMPLE_RATE = 16000
CHUNK_SAMPLES = 512


def environment():
    payload = {
        "os": f"{platform.system()} {platform.release()} ({platform.version()})",
        "machine": platform.machine(),
        "python": platform.python_version(),
    }
    for name, module in (("openwakeword", "openwakeword"),
                         ("onnxruntime", "onnxruntime")):
        try:
            import importlib.metadata as metadata

            payload[name] = metadata.version(module)
        except Exception:  # noqa: BLE001 - version reporting must not fail
            payload[name] = "unavailable"
    return payload


def rss_bytes():
    try:
        import psutil

        return psutil.Process().memory_info().rss
    except Exception:  # noqa: BLE001 - optional
        return None


def load_backend(selection):
    from openwakeword.model import Model

    kwargs = selection.loader_kwargs()
    return Model(
        wakeword_models=list(kwargs["wakeword_models"]),
        inference_framework="onnx",
        melspec_model_path=kwargs["melspec_model_path"],
        embedding_model_path=kwargs["embedding_model_path"],
    )


def read_wav(path):
    with wave.open(str(path), "rb") as handle:
        if handle.getnchannels() != 1 or handle.getsampwidth() != 2:
            raise SystemExit(f"{path} must be mono 16-bit PCM")
        rate = handle.getframerate()
        frames = handle.readframes(handle.getnframes())
    if rate != SAMPLE_RATE:
        raise SystemExit(f"{path} must be {SAMPLE_RATE} Hz, is {rate}")
    return frames


def command_artifacts(authority, _args):
    """The measured receptive field of every bundled classifier."""
    import onnxruntime as ort

    options = ort.SessionOptions()
    options.log_severity_level = 3
    rows = []
    for entry in authority.snapshot().entries:
        session = ort.InferenceSession(
            str(entry.artifact.path),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        frames = session.get_inputs()[0].shape[1]
        rows.append({
            "id": entry.id,
            "artifact": entry.artifact.file_name,
            "bytes": entry.artifact.byte_size,
            "inputFrames": frames,
            "receptiveFieldMs": receptive_field_ms(frames),
        })
    rows.sort(key=lambda row: row["id"])
    return {
        "measurement": "artifacts",
        "environment": environment(),
        "rows": rows,
        "minReceptiveFieldMs": min(row["receptiveFieldMs"] for row in rows),
        "maxReceptiveFieldMs": max(row["receptiveFieldMs"] for row in rows),
    }


def command_resources(authority, args):
    """Init time, RSS and detection latency for 1, 3 and max models."""
    available = list(authority.available_ids())
    sizes = sorted({1, 3, len(available)})
    silence = (b"\x00\x00" * CHUNK_SAMPLES)
    rows = []
    for size in sizes:
        if size > len(available):
            continue
        selection, errors = authority.resolve_selection(available[:size])
        if errors:
            raise SystemExit(f"selection failed: {[e.to_dict() for e in errors]}")

        before = rss_bytes()
        started = time.perf_counter()
        model = load_backend(selection)
        init_seconds = time.perf_counter() - started
        after = rss_bytes()

        # Warm up, then measure per-chunk detection latency.
        for _ in range(args.warmup):
            model.predict(_pcm(silence))
        latencies = []
        peak = after or 0
        for _ in range(args.iterations):
            tick = time.perf_counter()
            model.predict(_pcm(silence))
            latencies.append((time.perf_counter() - tick) * 1000.0)
            current = rss_bytes()
            if current is not None:
                peak = max(peak, current)

        latencies.sort()
        rows.append({
            "selectedModels": size,
            "wakeWordIds": list(selection.wake_word_ids),
            "initSeconds": round(init_seconds, 4),
            "rssBeforeBytes": before,
            "rssAfterBytes": after,
            "rssDeltaBytes": (after - before) if (before and after) else None,
            "peakRssBytes": peak or None,
            "detectionLatencyMsMedian": round(
                latencies[len(latencies) // 2], 4
            ),
            "detectionLatencyMsP95": round(
                latencies[int(len(latencies) * 0.95) - 1], 4
            ),
            "detectionLatencyMsMax": round(latencies[-1], 4),
            "measuredRearmMs": selection_receptive_field_ms(model.model_inputs),
            "chunkSamples": CHUNK_SAMPLES,
            "iterations": args.iterations,
        })
        del model
    return {
        "measurement": "resources",
        "environment": environment(),
        "rows": rows,
    }


def _pcm(data):
    import numpy as np

    return np.frombuffer(data, dtype=np.int16)


def command_scores(authority, args):
    """A full score/chunk trace of real audio through the production rules."""
    if not args.audio:
        raise SystemExit("scores needs at least one --audio file")
    selected = args.wake_words or list(authority.available_ids())[:1]
    selection, errors = authority.resolve_selection(selected)
    if errors:
        raise SystemExit(f"selection failed: {[e.to_dict() for e in errors]}")

    model = load_backend(selection)
    key_to_id = selection.model_key_to_id
    frames_by_key = dict(model.model_inputs)

    traces = []
    for audio_path in args.audio:
        data = read_wav(Path(audio_path))
        evaluator = WakeDetectionEvaluator(
            threshold=args.threshold,
            rearm_ms=selection_receptive_field_ms(frames_by_key),
            cooldown_ms=args.cooldown_ms,
        )
        model.reset() if hasattr(model, "reset") else None

        raw_hits = []
        accepted = []
        max_scores = {}
        position = 0
        frame_index = 0
        for offset in range(0, len(data) - CHUNK_SAMPLES * 2 + 1,
                            CHUNK_SAMPLES * 2):
            chunk = data[offset:offset + CHUNK_SAMPLES * 2]
            model.predict(_pcm(chunk))
            position += CHUNK_SAMPLES
            frame_index += 1
            candidates = []
            for key, scores in model.prediction_buffer.items():
                identifier = key_to_id.get(key)
                if identifier is None or not scores:
                    continue
                score = float(scores[-1])
                max_scores[identifier] = max(max_scores.get(identifier, 0.0), score)
                candidates.append(RawWakeCandidate(
                    canonical_wake_word_id=identifier,
                    raw_score=score,
                    frame_index=frame_index,
                    sample_position=position,
                    detector_generation=evaluator.generation,
                    model_key=key,
                ))
            above = [
                item for item in candidates
                if item.raw_score >= args.threshold
            ]
            for item in above:
                raw_hits.append(item.diagnostics())
            offered = evaluator.offer(candidates)
            if offered is None:
                continue
            detection = evaluator.accept(offered, activation_id=f"cal-{len(accepted)}")
            boundary = resolve_wake_audio_boundary(
                detection_sample_position=offered.sample_position,
                receptive_field_ms=receptive_field_ms(
                    frames_by_key.get(offered.model_key)
                ),
                pre_roll_ms=args.pre_roll_ms,
                sample_rate=SAMPLE_RATE,
            )
            accepted.append({
                "wakeWordId": detection.canonical_wake_word_id,
                "score": detection.score,
                "frameIndex": offered.frame_index,
                "samplePosition": offered.sample_position,
                "detectionTimeSeconds": offered.sample_position / SAMPLE_RATE,
                "boundary": boundary.to_dict(),
            })
            # The production latch would stay set until the safe input close;
            # for a pure detector trace it is released immediately so every
            # further spike of the same file stays visible as a duplicate.
            evaluator.release_latch(activation_id=detection.activation_id)

        traces.append({
            "audio": str(audio_path),
            "durationSeconds": round(len(data) / 2 / SAMPLE_RATE, 3),
            "chunks": frame_index,
            "maxScorePerWakeWord": {
                key: round(value, 6) for key, value in sorted(max_scores.items())
            },
            "rawCandidatesAboveThreshold": len(raw_hits),
            "acceptedDetections": accepted,
            "duplicateSpikes": max(0, len(raw_hits) - len(accepted)),
        })

    return {
        "measurement": "scores",
        "environment": environment(),
        "threshold": args.threshold,
        "cooldownMs": args.cooldown_ms,
        "preRollMs": args.pre_roll_ms,
        "wakeWordIds": list(selection.wake_word_ids),
        "measuredRearmMs": selection_receptive_field_ms(frames_by_key),
        "traces": traces,
    }


COMMANDS = {
    "artifacts": command_artifacts,
    "resources": command_resources,
    "scores": command_scores,
}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=sorted(COMMANDS))
    parser.add_argument("--asset-root", default=None)
    parser.add_argument("--audio", action="append", default=[])
    parser.add_argument("--wake-words", action="append", default=[])
    parser.add_argument("--threshold", type=float, default=0.5)
    parser.add_argument("--cooldown-ms", type=int, default=0)
    parser.add_argument("--pre-roll-ms", type=int, default=0)
    parser.add_argument("--iterations", type=int, default=200)
    parser.add_argument("--warmup", type=int, default=20)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    authority = WakeWordCatalogAuthority(
        asset_root=Path(args.asset_root) if args.asset_root else None
    )
    if authority.snapshot() is None:
        raise SystemExit(f"no wake-word catalog: {authority.load_error}")

    payload = COMMANDS[args.command](authority, args)
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        Path(args.out).write_text(rendered, encoding="utf-8", newline="\n")
    else:
        sys.stdout.write(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
