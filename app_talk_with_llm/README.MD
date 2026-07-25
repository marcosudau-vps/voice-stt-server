# OpenAI voice interface (Windows, CPU only)

Install the complete project environment from the repository root:

```powershell
.\install_windows_cpu.ps1
```

Verify all UI dependencies without opening a window, microphone, or model:

```powershell
.\.venv\Scripts\python.exe .\app_talk_with_llm\ui_openai_voice_interface.py --check
```

Start the application:

```powershell
$env:VOICESTT_FASTER_WHISPER_MODEL_ROOT = "S:\MODELS\stt\ctranslate2"
$env:VOICESTT_OFFLINE_MODELS = "1"
$env:VOICESTT_MODEL = "tiny"
$env:VOICESTT_REALTIME_MODEL = "tiny"
.\.venv\Scripts\python.exe .\app_talk_with_llm\ui_openai_voice_interface.py
```

The default speech output uses the installed Windows system voice. Azure and
ElevenLabs remain optional menu choices and require their respective
RealtimeTTS extras and credentials. STT is always initialized with `cpu`,
`int8`, Silero ONNX and the externally stored CTranslate2 models.
