"""Pure helpers for the Kroko single-native-identity rule (PR #15).

A Voice-STT process may operate at most one native Kroko model identity (see
:mod:`VoiceSTT.kroko.native_guard`). The helpers below decide that on plain
settings, *before* any engine, probe or scheduler exists, so an impossible
configuration is rejected with an understandable message instead of reaching
the native loader. No I/O besides the already loaded model manifest.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Tuple

from VoiceSTT_server.stt_model_management import normalize_engine

KROKO_ENGINE = "kroko_onnx"


def kroko_model_key(model: Any, manifest: Any = None) -> str:
    """Stable identity of a configured Kroko model (manifest id, else name)."""
    text = str(model or "").strip()
    if not text:
        return ""
    entry = None
    if manifest is not None:
        try:
            entry = manifest.get(text)
        except Exception:
            entry = None
    if entry is not None:
        return str(entry.id).lower()
    return Path(text).name.lower()


def kroko_lane_models(settings: Any, manifest: Any = None) -> List[Tuple[str, str, str]]:
    """``(lane, configured_model, identity_key)`` for every Kroko lane."""
    final_engine = normalize_engine(getattr(settings, "transcription_engine", ""))
    realtime_engine = normalize_engine(
        getattr(settings, "realtime_transcription_engine", None) or final_engine
    )
    lanes: List[Tuple[str, str, str]] = []
    if final_engine == KROKO_ENGINE:
        model = getattr(settings, "model", "")
        lanes.append(("final", str(model), kroko_model_key(model, manifest)))
    if realtime_engine == KROKO_ENGINE:
        model = getattr(settings, "realtime_model", None) or getattr(
            settings, "model", ""
        )
        lanes.append(("realtime", str(model), kroko_model_key(model, manifest)))
    return lanes


def enforce_kroko_single_identity(settings: Any, manifest: Any = None) -> None:
    """Reject two different Kroko models; share one instance for one model.

    Raises ``ValueError`` for final/realtime lanes that name two different
    Kroko models. Two lanes naming the same model are forced onto the shared
    instance (``use_main_model_for_realtime``), exactly like the existing
    same-engine/same-model rule, because a second native copy of the model
    is not a supported operating mode.
    """
    lanes = kroko_lane_models(settings, manifest)
    keys = {key for _lane, _model, key in lanes if key}
    if len(keys) > 1:
        raise ValueError(
            "Ein Voice-STT-Prozess darf nicht zwei unterschiedliche native "
            "Kroko-Modelle gleichzeitig betreiben. Final und Realtime "
            "muessen bei Kroko dasselbe Modell mit gemeinsamer Instanz "
            "(use_main_model_for_realtime) verwenden."
        )
    if len(lanes) == 2:
        settings.use_main_model_for_realtime = True


__all__ = [
    "KROKO_ENGINE",
    "enforce_kroko_single_identity",
    "kroko_lane_models",
    "kroko_model_key",
]
