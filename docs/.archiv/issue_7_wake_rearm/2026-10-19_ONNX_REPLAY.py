"""Issue #7: authorized WAV replay, not a live microphone qualification.

Inputs: alexa_pause.wav and jarvis_direct.wav from the pinned issue manifest.
No downloads, server connections or product mutations.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys

import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audio-dir", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from VoiceSTT.core.openwakeword_engine import OpenWakeWordEngine
    from VoiceSTT.core.wake_detection import WakeDetectionEvaluator
    from VoiceSTT.core.wakeword_catalog import WakeWordCatalogAuthority
    from tools.wakeword_calibration import read_wav

    authority = WakeWordCatalogAuthority()
    selection, errors = authority.admit_selection(
        ["alexa", "hey_jarvis"], requested_backend="onnx"
    )
    assert not errors, errors
    rows = []
    for fixture, expected, digest in (
        ("alexa_pause.wav", "alexa",
         "abae5a687cee97d120487c2a601509aba41d056b4428966959a1ef1e467b09b3"),
        ("jarvis_direct.wav", "hey_jarvis",
         "98e3f96e35cb736b5176c96159cf6e2416d50eb739faa2380320e181caf6d9b2"),
    ):
        path = args.audio_dir / fixture
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        data = read_wav(path)
        for mode in ("retained_control", "product_silence", "product_immediate"):
            np.random.seed(0)
            engine = OpenWakeWordEngine(selection=selection)
            evaluator = WakeDetectionEvaluator(engine=engine)
            try:
                first = None
                for offset in range(0, len(data) - 1280 + 1, 1280):
                    hits = evaluator.process(data[offset:offset + 1280])
                    if hits:
                        first = hits[0]
                        evaluator.accept(first, activation_id="replay-first")
                        break
                assert first and first.canonical_wake_word_id == expected
                if mode == "retained_control":
                    # Same model history, deliberately no upstream reset.
                    evaluator = WakeDetectionEvaluator(engine=engine)
                else:
                    assert evaluator.release_latch(activation_id="replay-first")
                second = []
                maxima = {}
                stimulus = data if mode == "product_immediate" else b"\0" * 160000
                for offset in range(0, len(stimulus) - 1280 + 1, 1280):
                    hits = evaluator.process(stimulus[offset:offset + 1280])
                    for key, score in evaluator.tracker.diagnostics()["lastScores"].items():
                        maxima[key] = max(maxima.get(key, 0.0), score)
                    for hit in hits:
                        second.append({
                            "wakeWordId": hit.canonical_wake_word_id,
                            "score": hit.peak_score,
                            "afterRearmMs": (offset + 1280) / 32,
                        })
                        evaluator.accept(hit, activation_id="replay-second")
                    if second:
                        break
                rows.append({
                    "fixture": fixture, "sha256": digest, "mode": mode,
                    "firstWakeWordId": first.canonical_wake_word_id,
                    "firstScore": first.peak_score,
                    "postRearmHits": second,
                    "postRearmMaxScores": maxima,
                })
            finally:
                engine.close()
    result = {
        "python": sys.version,
        "packages": {
            name: importlib.metadata.version(name)
            for name in ("numpy", "openwakeword", "onnxruntime")
        },
        "selection": list(selection.wake_word_ids),
        "backend": selection.backend,
        "rows": rows,
        "boundary": "Authorized recorded WAV replay; gate pause emulated, no wall-time delay, no hardware or server mutation.",
    }
    args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    for row in rows:
        if row["mode"] == "product_silence":
            assert not row["postRearmHits"], row
        elif row["mode"] == "product_immediate":
            assert len(row["postRearmHits"]) == 1, row
            assert row["postRearmHits"][0]["wakeWordId"] == row["firstWakeWordId"]
    assert rows[0]["postRearmHits"], "Alexa retained-history control did not reproduce"


if __name__ == "__main__":
    main()
