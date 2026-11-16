# Voice assistant example

The desktop example combines local VoiceSTT recognition, an OpenAI-compatible
chat endpoint and selectable speech synthesis in a small PyQt interface.

## Installation

Run the supported CPU installer from the repository root:

```powershell
.\install_windows_cpu.ps1
```

The compatibility wrapper `app_talk_with_llm\install_cpu.bat` invokes the same
installer and does not create a second virtual environment.

## Configuration

All non-secret defaults are in the `example_app` section of the root
`config.yaml`. The application reads that file automatically. Process
environment variables may temporarily override individual values.

The only local env file is the root `.env`. Put API credentials there, for
example `CUSTOM_API_CHAT_API_KEY`, when the selected chat endpoint requires
one. Never place credentials in `config.yaml`.

## Verification and start

Verify imports without opening a window, microphone or model:

```powershell
.\.venv\Scripts\python.exe .\app_talk_with_llm\ui_openai_voice_interface.py --check
```

Start the interface:

```powershell
.\.venv\Scripts\python.exe .\app_talk_with_llm\ui_openai_voice_interface.py
```

Generated log files are written below `logs/` and are intentionally not part of
the repository.
