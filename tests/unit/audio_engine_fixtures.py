"""Shared audio fixtures for the supported-engine tests.

Extracted from the removed ``test_additional_transcription_engines.py``
(V2 engine cleanup) because ``test_kroko_onnx_engine.py`` still uses the
golden-audio helpers. Pure test helpers; no engine imports.
"""

import re
import wave
from pathlib import Path

try:
    import numpy as np
except ModuleNotFoundError:
    np = None


AUDIO_DIR = Path(__file__).with_name("audio")


class AudioVector:
    def __init__(self, values):
        self.values = [float(value) for value in values]
        self.size = len(self.values)

    def __abs__(self):
        return AudioVector(abs(value) for value in self.values)

    def __truediv__(self, value):
        return AudioVector(item / value for item in self.values)

    def __mul__(self, value):
        return AudioVector(item * value for item in self.values)

    def max(self):
        return max(self.values)




def read_fixture_audio():
    wav_path = AUDIO_DIR / "LJ001-0002.wav"
    transcript_path = AUDIO_DIR / "LJ001-0002.txt"
    with wave.open(str(wav_path), "rb") as wav:
        sample_rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())
    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    audio = resample_audio(audio, sample_rate, 16000)
    expected = normalize_transcript(transcript_path.read_text(encoding="utf-8"))
    return audio, expected


def resample_audio(audio, source_rate, target_rate):
    if source_rate == target_rate:
        return audio
    target_length = int(len(audio) * target_rate / source_rate)
    source_positions = np.linspace(0.0, 1.0, num=len(audio), endpoint=False)
    target_positions = np.linspace(0.0, 1.0, num=target_length, endpoint=False)
    return np.interp(target_positions, source_positions, audio).astype(np.float32)


def normalize_transcript(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


