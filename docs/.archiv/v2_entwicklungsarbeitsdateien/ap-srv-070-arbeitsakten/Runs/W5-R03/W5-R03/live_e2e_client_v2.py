import asyncio
import json
import struct
import time
import uuid
import wave
import sys
import websockets

AUDIO_FILE = r"P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r03\tests\unit\audio\asr-reference.wav"

def encode_audio_packet(metadata, audio):
    metadata_bytes = json.dumps(metadata, separators=(",", ":")).encode("utf-8")
    return struct.pack("<I", len(metadata_bytes)) + metadata_bytes + bytes(audio)

async def run_live_e2e(ws_url="ws://127.0.0.1:18021/ws/v2", chunk_ms=100.0, speed=1.0):
    print(f"Connecting to {ws_url}...")
    async with websockets.connect(ws_url, ping_interval=None, max_size=10*1024*1024) as ws:
        # 1. Send Hello
        client_run_id = str(uuid.uuid4())
        hello = {
            "type": "hello",
            "supportedProtocolVersions": [2],
            "clientVersion": "2.0.0-qualification",
            "clientCommit": "934e3be7c78aa9358f9b42b9fa4dc282bed54d6c",
            "clientRunId": client_run_id,
            "requestedSession": {
                "trigger": {"manual": True, "wakeWord": False},
                "wakeWordIds": []
            },
            "runtimeSuppression": {
                "manual": False,
                "wakeWord": False
            }
        }
        await ws.send(json.dumps(hello))

        raw = await ws.recv()
        accept_msg = json.loads(raw)
        print(f"Handshake response: {accept_msg.get('type')}")
        assert accept_msg.get("type") == "hello.accepted", f"Expected hello.accepted, got {accept_msg}"
        session_id = accept_msg["sessionId"]
        print(f"Session admitted: {session_id}")

        # 2. Activate manual session
        act_cmd_id = str(uuid.uuid4())
        act_cmd = {
            "type": "activation_command",
            "protocolVersion": 2,
            "sessionId": session_id,
            "commandId": act_cmd_id,
            "action": "activate",
            "source": "manual"
        }
        await ws.send(json.dumps(act_cmd))
        print("Sent activate command")

        # Start receiver background task
        received_messages = []
        finals = []
        partials = []
        stop_receiving = asyncio.Event()

        async def receiver():
            try:
                while not stop_receiving.is_set():
                    try:
                        msg_text = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        data = json.loads(msg_text)
                        received_messages.append(data)
                        msg_type = data.get("type")
                        if msg_type == "transcript.final":
                            finals.append(data)
                            print(f"[FINAL] {data.get('text')}")
                        elif msg_type == "transcript.partial":
                            partials.append(data)
                        elif msg_type == "final":
                            finals.append(data)
                            print(f"[FINAL v1] {data.get('text')}")
                        elif msg_type == "segment.final":
                            finals.append(data)
                            print(f"[SEGMENT FINAL] {data.get('text')}")
                    except asyncio.TimeoutError:
                        continue
            except websockets.exceptions.ConnectionClosed:
                pass
            except Exception as e:
                print(f"Receiver error: {e}")

        recv_task = asyncio.create_task(receiver())

        # 3. Read audio file
        with wave.open(AUDIO_FILE, "rb") as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            sample_rate = wf.getframerate()
            total_frames = wf.getnframes()
            audio_bytes = wf.readframes(total_frames)
            duration_s = total_frames / float(sample_rate)

        print(f"Loaded audio: {duration_s:.2f}s, {sample_rate}Hz, {channels}ch, {sample_width}B/sample, {len(audio_bytes)} bytes")

        # Stream audio chunks
        bytes_per_sample = sample_width * channels
        frames_per_chunk = int(sample_rate * (chunk_ms / 1000.0))
        bytes_per_chunk = frames_per_chunk * bytes_per_sample

        stream_start_time = time.monotonic()
        total_sent_bytes = 0
        total_chunks = 0

        for offset in range(0, len(audio_bytes), bytes_per_chunk):
            chunk_data = audio_bytes[offset:offset + bytes_per_chunk]
            chunk_frames = len(chunk_data) // bytes_per_sample
            pkt = encode_audio_packet({
                "sampleRate": sample_rate,
                "channels": channels,
                "format": "pcm_s16le",
                "frames": chunk_frames
            }, chunk_data)
            await ws.send(pkt)
            total_sent_bytes += len(chunk_data)
            total_chunks += 1
            if speed > 0:
                chunk_dur = chunk_frames / float(sample_rate) / speed
                await asyncio.sleep(chunk_dur)

        stream_duration = time.monotonic() - stream_start_time
        print(f"Finished sending {total_chunks} audio chunks in {stream_duration:.2f}s")

        # 4. Deactivate session
        deact_cmd_id = str(uuid.uuid4())
        deact_cmd = {
            "type": "activation_command",
            "protocolVersion": 2,
            "sessionId": session_id,
            "commandId": deact_cmd_id,
            "action": "deactivate",
            "source": "manual"
        }
        await ws.send(json.dumps(deact_cmd))
        print("Sent deactivate command, waiting for remaining final transcripts...")

        # 5. Wait for trailing transcriptions
        wait_start = time.monotonic()
        last_final_count = len(finals)
        silence_rounds = 0

        while time.monotonic() - wait_start < 30.0:
            await asyncio.sleep(1.0)
            if len(finals) > last_final_count:
                last_final_count = len(finals)
                silence_rounds = 0
            else:
                silence_rounds += 1
                if silence_rounds >= 6 and len(finals) > 0:
                    break

        stop_receiving.set()
        await recv_task

        final_texts = [f.get("text", "").strip() for f in finals if f.get("text", "").strip()]
        full_transcript = " ".join(final_texts)

        summary = {
            "sessionId": session_id,
            "audioDurationSeconds": duration_s,
            "streamSendSeconds": stream_duration,
            "totalChunksSent": total_chunks,
            "totalMessagesReceived": len(received_messages),
            "finalCount": len(finals),
            "partialCount": len(partials),
            "transcript": full_transcript,
            "finals": finals
        }

        print("\n=== E2E RESULT ===")
        print(f"Final segments received: {len(finals)}")
        print(f"Full Transcript:\n{full_transcript}\n")
        return summary

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:18021/ws/v2"
    out_file = sys.argv[2] if len(sys.argv) > 2 else "e2e_result.json"
    result = asyncio.run(run_live_e2e(url, chunk_ms=100.0, speed=1.0))
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
