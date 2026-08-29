"""Reproducible wake-word score/audio/resource harness (AP-SRV-060).

Three independent measurements, all against the *real* OpenWakeWord backend and
the artifacts this build actually ships:

``artifacts``
    The measured receptive field of every bundled classifier. One prediction
    frame advances the stream by 1280 samples (80 ms at 16 kHz) and the
    embedding model consumes 76 melspectrogram frames (760 ms), so a classifier
    with ``N`` input frames still sees the same utterance for
    ``(N - 1) * 80 + 760`` ms. Since AP-SRV-060 C3 this is a *diagnostic*
    measurement only: no setting range and no audio boundary is derived from it.

``resources``
    Init/startup time, RSS before/after, peak RSS and per-chunk detection
    latency for 1, 3 and the maximum selectable number of models.

``scores``
    A full prediction-frame trace of one or more WAV files through the *real*
    production rules of AP-SRV-060 C3: the one
    :class:`~VoiceSTT.core.openwakeword_engine.OpenWakeWordEngine`, the
    :class:`~VoiceSTT.core.wake_detection.WakeHitTracker` with its score
    threshold and minimum consecutive prediction frames, the finalized hit
    regions and the wake boundary each one establishes at its operational zero
    point. ``--min-frames`` and ``--detector-gain`` sweep exactly the two knobs
    the calibration is missing.

Positive wake-word recordings are *not* part of the repository. Running
``scores`` against negative material characterises false positives only; the
threshold, minimum-frame, cooldown, pre-roll and gain defaults that depend on
real positive speech stay ``EVIDENCE_BLOCKED`` and are deliberately not
simulated.

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

from VoiceSTT.core.openwakeword_engine import (  # noqa: E402
    PREDICTION_FRAME_SAMPLES,
    OpenWakeWordEngine,
)
from VoiceSTT.core.wake_audio_boundary import resolve_wake_audio_boundary  # noqa: E402
from VoiceSTT.core.wake_detection import (  # noqa: E402
    WakeAttemptPolicy,
    WakeHitTracker,
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


def load_backend(selection, **engine_options):
    """The one live wake engine of this measurement.

    It runs on the *common* backend the admission chose for the whole
    selection - the harness never picks a framework of its own.
    """
    return OpenWakeWordEngine(selection=selection, **engine_options)


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
        artifact = entry.artifact_for("onnx")
        if artifact is None:
            continue
        session = ort.InferenceSession(
            str(artifact.path),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )
        frames = session.get_inputs()[0].shape[1]
        rows.append({
            "id": entry.id,
            "artifact": artifact.file_name,
            "bytes": artifact.byte_size,
            "inputFrames": frames,
            "healthyBackends": list(entry.healthy_backends),
            "inputFramesNote": "diagnostic only since C3",
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
        selection, errors = authority.admit_selection(available[:size])
        if errors:
            raise SystemExit(f"selection failed: {[e.to_dict() for e in errors]}")

        before = rss_bytes()
        started = time.perf_counter()
        engine = load_backend(selection)
        init_seconds = time.perf_counter() - started
        after = rss_bytes()

        # Warm up, then measure per-chunk detection latency.
        for _ in range(args.warmup):
            engine.process(silence)
        latencies = []
        peak = after or 0
        for _ in range(args.iterations):
            tick = time.perf_counter()
            engine.process(silence)
            latencies.append((time.perf_counter() - tick) * 1000.0)
            current = rss_bytes()
            if current is not None:
                peak = max(peak, current)

        latencies.sort()
        rows.append({
            "selectedModels": size,
            "wakeWordIds": list(selection.wake_word_ids),
            "backend": selection.backend,
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
            "measuredReceptiveFieldMs": selection_receptive_field_ms(
                engine.input_frames
            ),
            "chunkSamples": CHUNK_SAMPLES,
            "predictionFrames": engine.frame_index,
            "iterations": args.iterations,
        })
        engine.close()
        del engine
    return {
        "measurement": "resources",
        "environment": environment(),
        "rows": rows,
    }


def _pcm(data):
    import numpy as np

    return np.frombuffer(data, dtype=np.int16)


def command_scores(authority, args):
    """A full prediction-frame trace of real audio through the C3 rules."""
    if not args.audio:
        raise SystemExit("scores needs at least one --audio file")
    selected = args.wake_words or list(authority.available_ids())[:1]
    selection, errors = authority.admit_selection(selected)
    if errors:
        raise SystemExit(f"selection failed: {[e.to_dict() for e in errors]}")

    policy = WakeAttemptPolicy(
        sensitivity=args.threshold,
        min_consecutive_prediction_frames=args.min_frames,
        detector_gain=args.detector_gain,
        cooldown_ms=args.cooldown_ms,
        pre_roll_ms=args.pre_roll_ms,
    )

    traces = []
    for audio_path in args.audio:
        data = read_wav(Path(audio_path))
        engine = load_backend(
            selection,
            detector_gain=args.detector_gain,
            noise_suppression_enabled=args.noise_suppression,
            vad_threshold=args.vad_threshold,
        )
        tracker = WakeHitTracker(policy_supplier=lambda: policy)

        frames_above = 0
        max_scores = {}
        hits = []
        prediction_frames = 0
        for offset in range(0, len(data) - CHUNK_SAMPLES * 2 + 1,
                            CHUNK_SAMPLES * 2):
            chunk = data[offset:offset + CHUNK_SAMPLES * 2]
            for frame in engine.process(chunk):
                prediction_frames += 1
                for identifier, score in frame.scores.items():
                    max_scores[identifier] = max(
                        max_scores.get(identifier, 0.0), score
                    )
                    if score >= args.threshold:
                        frames_above += 1
                hit = tracker.observe(frame.scores, end_sample=frame.end_sample)
                if hit is None:
                    continue
                boundary = resolve_wake_audio_boundary(
                    operational_zero_point_sample=hit.operational_zero_point_sample,
                    pre_roll_ms=args.pre_roll_ms,
                    sample_rate=SAMPLE_RATE,
                )
                hits.append({
                    "wakeWordId": hit.canonical_wake_word_id,
                    "peakScore": round(hit.peak_score, 6),
                    "startFrameIndex": hit.start_frame_index,
                    "qualificationFrameIndex": hit.qualification_frame_index,
                    "finalizationFrameIndex": hit.finalization_frame_index,
                    "predictionFrameCount": hit.prediction_frame_count,
                    "zeroPointSeconds": round(
                        hit.operational_zero_point_sample / SAMPLE_RATE, 4
                    ),
                    "boundary": boundary.to_dict(),
                })

        traces.append({
            "audio": str(audio_path),
            "durationSeconds": round(len(data) / 2 / SAMPLE_RATE, 3),
            "chunks": len(range(0, len(data) - CHUNK_SAMPLES * 2 + 1,
                                CHUNK_SAMPLES * 2)),
            "predictionFrames": prediction_frames,
            "maxScorePerWakeWord": {
                key: round(value, 6) for key, value in sorted(max_scores.items())
            },
            "predictionFramesAboveThreshold": frames_above,
            # The whole point of the C3 model: many frames above the threshold
            # are one logical hit, not many.
            "finalizedWakeHits": hits,
            "logicalHitCount": len(hits),
        })
        engine.close()

    return {
        "measurement": "scores",
        "environment": environment(),
        "backend": selection.backend,
        "threshold": args.threshold,
        "minConsecutivePredictionFrames": args.min_frames,
        "detectorGain": args.detector_gain,
        "vadThreshold": args.vad_threshold,
        "noiseSuppressionEnabled": bool(args.noise_suppression),
        "cooldownMs": args.cooldown_ms,
        "preRollMs": args.pre_roll_ms,
        "wakeWordIds": list(selection.wake_word_ids),
        "predictionFrameSamples": PREDICTION_FRAME_SAMPLES,
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
    parser.add_argument("--min-frames", type=int, default=1)
    parser.add_argument("--detector-gain", type=float, default=1.0)
    parser.add_argument("--vad-threshold", type=float, default=0.0)
    parser.add_argument("--noise-suppression", action="store_true")
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
