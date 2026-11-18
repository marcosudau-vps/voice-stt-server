import asyncio
import json
import struct
import time
import uuid
import wave
import sys
import websockets

def encode_audio_packet(metadata, audio):
    metadata_bytes = json.dumps(metadata, separators=(",", ":")).encode("utf-8")
    return struct.pack("<I", len(metadata_bytes)) + metadata_bytes + bytes(audio)

async def run_live_session(audio_file, ws_url="ws://127.0.0.1:18022/ws/v2", chunk_ms=100.0, speed=1.0):
    print(f"Connecting to {ws_url}...", flush=True)
    async with websockets.connect(ws_url, ping_interval=None, max_size=16*1024*1024) as ws:
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
        print(f"Handshake response: {accept_msg.get('type')}", flush=True)
        assert accept_msg.get("type") == "hello.accepted", f"Expected hello.accepted, got {accept_msg}"
        session_id = accept_msg["sessionId"]
        print(f"Session admitted: {session_id}", flush=True)

        # Message queues and collectors
        all_messages = []
        transcripts = []
        stop_event = asyncio.Event()

        async def reader():
            try:
                while not stop_event.is_set():
                    try:
                        msg_text = await asyncio.wait_for(ws.recv(), timeout=0.5)
                        msg = json.loads(msg_text)
                        all_messages.append(msg)
                        msg_type = msg.get("type")
                        if msg_type == "transcription.completed":
                            text = msg.get("text", "").strip()
                            transcripts.append(msg)
                            print(f"[TRANSCRIPTION COMPLETED] {text}", flush=True)
                        elif msg_type == "activation.phase_changed":
                            print(f"[PHASE CHANGED] -> {msg.get('phase')}", flush=True)
                        elif msg_type == "segment.recording_started":
                            print(f"[SEGMENT RECORDING STARTED] id={msg.get('segmentId')}", flush=True)
                        elif msg_type == "segment.recording_ended":
                            print(f"[SEGMENT RECORDING ENDED] id={msg.get('segmentId')}, reason={msg.get('reason')}", flush=True)
                        elif msg_type == "command.ack":
                            print(f"[COMMAND ACK] id={msg.get('commandId')}, result={msg.get('result')}", flush=True)
                        elif msg_type == "activation.completed":
                            print(f"[ACTIVATION COMPLETED]", flush=True)
                    except asyncio.TimeoutError:
                        continue
            except websockets.exceptions.ConnectionClosed:
                print("Connection closed by peer in reader", flush=True)
            except Exception as e:
                print(f"Reader exception: {e}", flush=True)

        reader_task = asyncio.create_task(reader())

        # 2. Activate manual trigger
        act_cmd_id = str(uuid.uuid4())
        act_cmd = {
            "type": "activation.command",
            "protocolVersion": 2,
            "sessionId": session_id,
            "commandId": act_cmd_id,
            "action": "activate",
            "source": "manual"
        }
        await ws.send(json.dumps(act_cmd))
        print("Sent activate command", flush=True)

        # Wait to observe activate ack
        activation_id = None
        for _ in range(50):
            await asyncio.sleep(0.1)
            for m in all_messages:
                if m.get("type") == "command.ack" and m.get("commandId") == act_cmd_id:
                    activation_id = m.get("activationId")
                    break
            if activation_id:
                break

        print(f"Observed activationId: {activation_id}", flush=True)
        assert activation_id is not None, f"Failed to obtain activationId from server, messages: {all_messages}"

        # 3. Read audio file
        with wave.open(audio_file, "rb") as wf:
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            sample_rate = wf.getframerate()
            total_frames = wf.getnframes()
            audio_bytes = wf.readframes(total_frames)
            duration_s = total_frames / float(sample_rate)

        print(f"Audio file: {duration_s:.2f}s, {sample_rate}Hz, {channels}ch, {len(audio_bytes)} bytes", flush=True)

        # 4. Stream audio chunks
        bytes_per_sample = sample_width * channels
        frames_per_chunk = int(sample_rate * (chunk_ms / 1000.0))
        bytes_per_chunk = frames_per_chunk * bytes_per_sample

        stream_start_time = time.monotonic()
        total_chunks = 0
        total_sent_bytes = 0

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
        print(f"Streamed {total_chunks} chunks ({total_sent_bytes} bytes) in {stream_duration:.2f}s", flush=True)

        # 5. Send Finish command
        finish_cmd_id = str(uuid.uuid4())
        finish_cmd = {
            "type": "activation.command",
            "protocolVersion": 2,
            "sessionId": session_id,
            "commandId": finish_cmd_id,
            "action": "finish",
            "activationId": activation_id
        }
        await ws.send(json.dumps(finish_cmd))
        print("Sent finish command", flush=True)

        # 6. Wait for remaining transcriptions and activation drain
        print("Waiting for trailing transcriptions...", flush=True)
        wait_start = time.monotonic()
        last_count = len(transcripts)
        silence_count = 0

        while time.monotonic() - wait_start < 25.0:
            await asyncio.sleep(1.0)
            current_count = len(transcripts)
            if current_count > last_count:
                last_count = current_count
                silence_count = 0
            else:
                silence_count += 1
                # If we received transcriptions and have observed activation completion or at least 5s silence
                activation_completed = any(m.get("type") == "activation.completed" for m in all_messages)
                if activation_completed and silence_count >= 3:
                    print("Activation completed and trailing silence settled.", flush=True)
                    break
                elif silence_count >= 8 and len(transcripts) > 0:
                    print("Settled after trailing silence.", flush=True)
                    break

        stop_event.set()
        await reader_task

        texts = [t.get("text", "").strip() for t in transcripts if t.get("text", "").strip()]
        full_transcript = " ".join(texts)

        return {
            "sessionId": session_id,
            "audioDurationSeconds": duration_s,
            "streamSendSeconds": stream_duration,
            "totalChunksSent": total_chunks,
            "totalMessagesReceived": len(all_messages),
            "transcriptCount": len(transcripts),
            "fullTranscript": full_transcript,
            "transcripts": transcripts,
            "allMessages": all_messages
        }

if __name__ == "__main__":
    audio_path = sys.argv[1] if len(sys.argv) > 1 else r"P:\GithubRepos\marcosudau-vps\voice-stt-server\workspaces\ap-srv-070-w5-r03\tests\unit\audio\asr-reference.wav"
    url = sys.argv[2] if len(sys.argv) > 2 else "ws://127.0.0.1:18022/ws/v2"
    out_file = sys.argv[3] if len(sys.argv) > 3 else "result.json"
    result = asyncio.run(run_live_session(audio_path, url))
    print("\n===============================")
    print("FINAL TRANSCRIPT:")
    print(result["fullTranscript"])
    print("===============================\n")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)
