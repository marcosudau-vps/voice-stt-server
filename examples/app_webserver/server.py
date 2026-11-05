"""Launch the shared CPU-only multi-user web server on the historic port."""

import os

from VoiceSTT_server.server import main


if __name__ == "__main__":
    main(
        [
            "--host",
            os.getenv("VOICESTT_HOST", "0.0.0.0"),
            "--port",
            os.getenv("VOICESTT_PORT", "5025"),
            "--model",
            os.getenv("VOICESTT_MODEL", "small"),
            "--realtime-model",
            os.getenv(
                "VOICESTT_REALTIME_MODEL",
                "Kroko-DE-Community-64-L-Streaming-001.data",
            ),
            "--realtime-engine",
            os.getenv("VOICESTT_REALTIME_ENGINE", "kroko_onnx"),
            "--language",
            os.getenv("VOICESTT_LANGUAGE", "de"),
            "--device",
            "cpu",
            "--compute-type",
            os.getenv("VOICESTT_COMPUTE_TYPE", "int8"),
        ]
    )
