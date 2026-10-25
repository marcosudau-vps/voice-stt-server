"""OpenAI-compatible HTTP endpoints, independent of the ASGI application factory.

No imports from api_fastapi_server.server: the shared service owns inference,
model authority and telemetry while this module owns HTTP/SSE mechanics.
All collaborators are explicitly supplied by create_openai_router.
"""

import asyncio
import math
import threading
import time
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from VoiceSTT_server.openai_compat import (
    OpenAIRequestError,
    format_caption_response,
    format_json_response,
    openai_error,
    parse_transcription_form,
    sse_data,
    validate_audio_filename,
)


def create_openai_router(
    *,
    service,
    settings,
    authenticate_openai,
    normalized_client_id,
    decode_audio_float32,
    process_memory_snapshot,
    sample_rate,
    logger,
):
    """Register the unchanged OpenAI contract without importing server.py."""

    router = APIRouter()

    @router.get("/v1/models")
    async def openai_models(request: Request):
        auth_error = await authenticate_openai(request)
        if auth_error is not None:
            return auth_error
        models = []
        for entry in service.model_catalog():
            models.append({
                "id": entry["id"],
                "object": "model",
                "created": 0,
                "owned_by": "local",
                "engine": entry["engine"],
                "loaded": entry["loaded"],
                "lanes": entry["lanes"],
            })
        if not any(item["id"] == "whisper-1" for item in models):
            models.insert(0, {
                "id": "whisper-1", "object": "model", "created": 0,
                "owned_by": "voicestt", "engine": "routing_alias",
                "loaded": True, "lanes": ["final"],
            })
        return JSONResponse({"object": "list", "data": models})

    @router.post("/v1/audio/transcriptions")
    async def openai_transcriptions(request: Request):
        request_id = uuid.uuid4().hex
        supplied_client_id = request.headers.get("x-voicestt-client-id")
        client_id = (
            normalized_client_id(supplied_client_id)
            if supplied_client_id
            else None
        )
        request_started = time.monotonic()
        response_headers = {"X-Request-ID": request_id}
        resolution = None
        archived_audio = None

        def emit_http_transcription(event, severity="info", **fields):
            return service.events.emit(
                "transcription",
                event,
                severity=severity,
                transport="http",
                clientId=client_id,
                sessionId=request_id,
                requestId=request_id,
                transcriptionId=request_id,
                **fields,
            )
        if not settings.openai_api_enabled:
            emit_http_transcription(
                "transcription.rejected",
                severity="warning",
                reason="api_disabled",
            )
            return JSONResponse(
                openai_error("Die OpenAI-kompatible API ist deaktiviert."),
                status_code=404,
                headers=response_headers,
            )
        auth_error = await authenticate_openai(request)
        if auth_error is not None:
            emit_http_transcription(
                "transcription.rejected",
                severity="warning",
                reason="authentication_failed",
            )
            try:
                auth_error.headers["X-Request-ID"] = request_id
            except Exception:
                pass
            return auth_error
        try:
            form = await request.form()
            upload = form.get("file")
            if upload is None or not hasattr(upload, "read"):
                raise OpenAIRequestError("Das Feld 'file' ist erforderlich.", "file")
            validate_audio_filename(getattr(upload, "filename", ""))
            parameters = parse_transcription_form(form)
            form_override = str(
                form.get("voicestt_model") or form.get("model_override") or ""
            ).strip()
            header_override = str(request.headers.get("x-voicestt-model") or "").strip()
            override = form_override or header_override
            override_source = (
                "multipart.voicestt_model" if form_override
                else ("header.x-voicestt-model" if header_override else None)
            )
            resolution = service.resolve_openai_model(
                parameters.model,
                override=override,
                override_source=override_source,
            )
            lane = resolution["lane"]
            response_headers.update({
                "X-VoiceSTT-Requested-Model": resolution["requested"],
                "X-VoiceSTT-Resolved-Model": resolution["resolved"],
                "X-VoiceSTT-Route": resolution["lane"],
            })
            if resolution["override"]:
                response_headers["X-VoiceSTT-Override-Model"] = resolution["override"]
            if resolution["overrideSource"]:
                response_headers["X-VoiceSTT-Override-Source"] = resolution["overrideSource"]
            audio_bytes = await upload.read(settings.openai_max_file_bytes + 1)
            if len(audio_bytes) > settings.openai_max_file_bytes:
                raise OpenAIRequestError(
                    f"Die Audiodatei überschreitet das Serverlimit von {settings.openai_max_file_bytes} Byte.",
                    "file",
                    "file_too_large",
                    413,
                )
            archived_audio = service.audit.archive_audio(
                audio_bytes,
                getattr(upload, "filename", "audio"),
                request_id,
            )
            samples = await asyncio.to_thread(decode_audio_float32, audio_bytes)
            duration = len(samples) / float(sample_rate)
            selected_language = parameters.language or settings.language
            emit_http_transcription(
                "transcription.accepted",
                filename=getattr(upload, "filename", None),
                bytes=len(audio_bytes),
                requestedModel=resolution["requested"],
                resolvedModel=resolution["resolved"],
                lane=lane,
                stream=parameters.stream,
            )
            service.audit.event(
                "transcription.started",
                transport="http",
                clientId=client_id,
                sessionId=request_id,
                transcriptionId=request_id,
                requestId=request_id,
                filename=getattr(upload, "filename", None),
                bytes=len(audio_bytes),
                audioDurationSeconds=duration,
                requestedModel=resolution["requested"],
                overrideModel=resolution["override"],
                overrideSource=resolution["overrideSource"],
                resolvedModel=resolution["resolved"],
                lane=lane,
                language=selected_language,
                stream=parameters.stream,
                responseFormat=parameters.response_format,
                archivedAudio=archived_audio,
            )
            emit_http_transcription(
                "transcription.started",
                filename=getattr(upload, "filename", None),
                bytes=len(audio_bytes),
                audioDurationMs=round(duration * 1000.0, 3),
                requestedModel=resolution["requested"],
                resolvedModel=resolution["resolved"],
                lane=lane,
                language=selected_language,
                stream=parameters.stream,
                responseFormat=parameters.response_format,
            )
            request_options = {
                "prompt": parameters.prompt,
                "temperature": parameters.temperature,
                "threshold": parameters.threshold,
                "timestamp_granularities": parameters.timestamp_granularities,
            }

            if parameters.stream:
                queue = asyncio.Queue()
                event_loop = asyncio.get_running_loop()
                first_delta_lock = threading.Lock()
                first_delta_seen = False
                first_delta_at = None
                last_delta_at = None
                realtime_intervals_ms = []
                realtime_event_count = 0

                def record_http_first_text(text):
                    nonlocal first_delta_seen
                    if str(text or "").strip():
                        with first_delta_lock:
                            if not first_delta_seen:
                                first_delta_seen = True
                                service.performance.event(
                                    "http.first_text",
                                    transport="http",
                                    clientId=client_id,
                                    sessionId=request_id,
                                    transcriptionId=request_id,
                                    requestId=request_id,
                                    lane=lane,
                                    engine=service.active_models()[lane]["engine"],
                                    model=resolution["resolved"],
                                    timeToFirstTextMs=round(
                                        (time.monotonic() - request_started) * 1000.0,
                                        3,
                                    ),
                                    audioDurationSeconds=round(duration, 6),
                                    memory=process_memory_snapshot(),
                                )

                def stream_callback(text, _detail):
                    nonlocal first_delta_at, last_delta_at, realtime_event_count
                    record_http_first_text(text)
                    now = time.monotonic()
                    with first_delta_lock:
                        if first_delta_at is None:
                            first_delta_at = now
                        interval_ms = (
                            round((now - last_delta_at) * 1000.0, 3)
                            if last_delta_at is not None
                            else None
                        )
                        if interval_ms is not None:
                            realtime_intervals_ms.append(interval_ms)
                        last_delta_at = now
                        realtime_event_count += 1
                        sequence = realtime_event_count
                    if settings.realtime_log_detail == "events":
                        service.performance.event(
                            "transcription.realtime_emitted",
                            transport="http",
                            clientId=client_id,
                            sessionId=request_id,
                            transcriptionId=request_id,
                            requestId=request_id,
                            sequence=sequence,
                            sincePreviousMs=interval_ms,
                            sinceRequestStartMs=round(
                                (now - request_started) * 1000.0,
                                3,
                            ),
                            characterCount=len(str(text or "")),
                        )
                    event_loop.call_soon_threadsafe(
                        queue.put_nowait,
                        {"type": "transcript.text.delta", "delta": text},
                    )

                def emit_http_realtime_summary():
                    if settings.realtime_log_detail == "off":
                        return
                    with first_delta_lock:
                        intervals = sorted(realtime_intervals_ms)
                        count = realtime_event_count
                        first_realtime_at = first_delta_at

                    def selected_percentile(fraction):
                        if not intervals:
                            return None
                        index = max(
                            0,
                            min(
                                len(intervals) - 1,
                                math.ceil(len(intervals) * fraction) - 1,
                            ),
                        )
                        return round(intervals[index], 3)

                    service.performance.event(
                        "transcription.performance_summary",
                        transport="http",
                        clientId=client_id,
                        sessionId=request_id,
                        transcriptionId=request_id,
                        requestId=request_id,
                        realtimeEventCount=count,
                        averageRealtimeIntervalMs=(
                            round(sum(intervals) / len(intervals), 3)
                            if intervals
                            else None
                        ),
                        minRealtimeIntervalMs=(
                            min(intervals) if intervals else None
                        ),
                        maxRealtimeIntervalMs=(
                            max(intervals) if intervals else None
                        ),
                        p50RealtimeIntervalMs=selected_percentile(0.50),
                        p95RealtimeIntervalMs=selected_percentile(0.95),
                        timeToFirstRealtimeMs=(
                            round(
                                (first_realtime_at - request_started)
                                * 1000.0,
                                3,
                            )
                            if first_realtime_at is not None
                            else None
                        ),
                        timeToFinalMs=round(
                            (time.monotonic() - request_started) * 1000.0,
                            3,
                        ),
                    )

                request_options["stream_callback"] = stream_callback

                async def event_stream():
                    task = asyncio.create_task(asyncio.to_thread(
                        service.transcribe_openai,
                        lane,
                        samples,
                        selected_language,
                        request_options,
                        correlation_id=request_id,
                        client_id=client_id,
                    ))
                    while not task.done() or not queue.empty():
                        try:
                            yield sse_data(await asyncio.wait_for(queue.get(), timeout=0.1))
                        except asyncio.TimeoutError:
                            continue
                    try:
                        inference = await task
                    except Exception as exc:
                        service.audit.event(
                            "transcription.failed",
                            transport="http",
                            clientId=client_id,
                            sessionId=request_id,
                            transcriptionId=request_id,
                            requestId=request_id,
                            resolvedModel=resolution["resolved"],
                            lane=lane,
                            latencyMs=round((time.monotonic() - request_started) * 1000, 3),
                            error=str(exc),
                        )
                        emit_http_transcription(
                            "transcription.failed",
                            severity="error",
                            resolvedModel=resolution["resolved"],
                            lane=lane,
                            latencyMs=round(
                                (time.monotonic() - request_started) * 1000,
                                3,
                            ),
                            error=str(exc),
                        )
                        yield sse_data({"type": "error", "error": openai_error(str(exc))["error"]})
                        return
                    from VoiceSTT.transcription_engines import TranscriptionInfo, TranscriptionResult
                    result = TranscriptionResult(
                        text=inference.text,
                        info=TranscriptionInfo(language=selected_language),
                        details=inference.details or {},
                    )
                    payload = format_json_response(parameters, result, duration)
                    if parameters.response_format == "diarized_json":
                        for segment in payload["segments"]:
                            yield sse_data(segment)
                    done = {
                        "type": "transcript.text.done",
                        "text": inference.text,
                        "usage": payload.get("usage"),
                    }
                    if "logprobs" in parameters.include:
                        done["logprobs"] = payload.get("logprobs", [])
                    record_http_first_text(inference.text)
                    service.audit.event(
                        "transcription.completed",
                        transport="http",
                        clientId=client_id,
                        sessionId=request_id,
                        transcriptionId=request_id,
                        requestId=request_id,
                        resolvedModel=resolution["resolved"],
                        lane=lane,
                        language=selected_language,
                        audioDurationSeconds=duration,
                        queueDelayMs=round(inference.queue_delay * 1000, 3),
                        inferenceMs=round(inference.inference_duration * 1000, 3),
                        latencyMs=round((time.monotonic() - request_started) * 1000, 3),
                        text=inference.text,
                        archivedAudio=archived_audio,
                        stream=True,
                    )
                    emit_http_transcription(
                        "transcription.completed",
                        resolvedModel=resolution["resolved"],
                        lane=lane,
                        language=selected_language,
                        audioDurationMs=round(duration * 1000.0, 3),
                        queueDelayMs=round(inference.queue_delay * 1000, 3),
                        inferenceMs=round(
                            inference.inference_duration * 1000,
                            3,
                        ),
                        totalLatencyMs=round(
                            (time.monotonic() - request_started) * 1000,
                            3,
                        ),
                        text=inference.text,
                        stream=True,
                    )
                    service.performance.event(
                        "http.completed",
                        transport="http",
                        clientId=client_id,
                        sessionId=request_id,
                        transcriptionId=request_id,
                        requestId=request_id,
                        lane=lane,
                        engine=service.active_models()[lane]["engine"],
                        model=resolution["resolved"],
                        stream=True,
                        success=True,
                        audioDurationSeconds=round(duration, 6),
                        apiLatencyMs=round(
                            (time.monotonic() - request_started) * 1000.0, 3
                        ),
                        memory=process_memory_snapshot(),
                    )
                    emit_http_realtime_summary()
                    yield sse_data(done)

                return StreamingResponse(
                    event_stream(),
                    media_type="text/event-stream",
                    headers={
                        **response_headers,
                        "Cache-Control": "no-cache",
                        "X-Accel-Buffering": "no",
                    },
                )

            inference = await asyncio.to_thread(
                service.transcribe_openai,
                lane,
                samples,
                selected_language,
                request_options,
                correlation_id=request_id,
                client_id=client_id,
            )
            from VoiceSTT.transcription_engines import TranscriptionInfo, TranscriptionResult
            result = TranscriptionResult(
                text=inference.text,
                info=TranscriptionInfo(language=selected_language),
                details=inference.details or {},
            )
            service.audit.event(
                "transcription.completed",
                transport="http",
                clientId=client_id,
                sessionId=request_id,
                transcriptionId=request_id,
                requestId=request_id,
                resolvedModel=resolution["resolved"],
                lane=lane,
                language=selected_language,
                audioDurationSeconds=duration,
                queueDelayMs=round(inference.queue_delay * 1000, 3),
                inferenceMs=round(inference.inference_duration * 1000, 3),
                latencyMs=round((time.monotonic() - request_started) * 1000, 3),
                text=inference.text,
                archivedAudio=archived_audio,
                stream=False,
            )
            emit_http_transcription(
                "transcription.completed",
                resolvedModel=resolution["resolved"],
                lane=lane,
                language=selected_language,
                audioDurationMs=round(duration * 1000.0, 3),
                queueDelayMs=round(inference.queue_delay * 1000, 3),
                inferenceMs=round(inference.inference_duration * 1000, 3),
                totalLatencyMs=round(
                    (time.monotonic() - request_started) * 1000,
                    3,
                ),
                text=inference.text,
                stream=False,
            )
            service.performance.event(
                "http.completed",
                transport="http",
                clientId=client_id,
                sessionId=request_id,
                transcriptionId=request_id,
                requestId=request_id,
                lane=lane,
                engine=service.active_models()[lane]["engine"],
                model=resolution["resolved"],
                stream=False,
                success=True,
                audioDurationSeconds=round(duration, 6),
                apiLatencyMs=round(
                    (time.monotonic() - request_started) * 1000.0, 3
                ),
                memory=process_memory_snapshot(),
            )
            if settings.realtime_log_detail != "off":
                service.performance.event(
                    "transcription.performance_summary",
                    transport="http",
                    clientId=client_id,
                    sessionId=request_id,
                    transcriptionId=request_id,
                    requestId=request_id,
                    realtimeEventCount=0,
                    timeToFinalMs=round(
                        (time.monotonic() - request_started) * 1000.0,
                        3,
                    ),
                )
            if parameters.response_format in {"text", "srt", "vtt"}:
                body = format_caption_response(parameters, result, duration)
                media_type = "text/vtt" if parameters.response_format == "vtt" else "text/plain"
                return Response(content=body, media_type=media_type, headers=response_headers)
            return JSONResponse(
                format_json_response(parameters, result, duration),
                headers=response_headers,
            )
        except OpenAIRequestError as exc:
            service.audit.event(
                "transcription.rejected",
                transport="http",
                clientId=client_id,
                sessionId=request_id,
                transcriptionId=request_id,
                requestId=request_id,
                requestedModel=(resolution or {}).get("requested"),
                latencyMs=round((time.monotonic() - request_started) * 1000, 3),
                error=str(exc),
                param=exc.param,
                code=exc.code,
            )
            emit_http_transcription(
                "transcription.rejected",
                severity="warning",
                requestedModel=(resolution or {}).get("requested"),
                latencyMs=round(
                    (time.monotonic() - request_started) * 1000,
                    3,
                ),
                error=str(exc),
                param=exc.param,
                code=exc.code,
            )
            return JSONResponse(
                openai_error(exc, exc.param, exc.code),
                status_code=exc.status_code,
                headers=response_headers,
            )
        except Exception as exc:
            logger.exception("OpenAI-kompatible Transkription fehlgeschlagen")
            service.audit.event(
                "transcription.failed",
                transport="http",
                clientId=client_id,
                sessionId=request_id,
                transcriptionId=request_id,
                requestId=request_id,
                requestedModel=(resolution or {}).get("requested"),
                resolvedModel=(resolution or {}).get("resolved"),
                latencyMs=round((time.monotonic() - request_started) * 1000, 3),
                error=str(exc),
            )
            emit_http_transcription(
                "transcription.failed",
                severity="error",
                requestedModel=(resolution or {}).get("requested"),
                resolvedModel=(resolution or {}).get("resolved"),
                latencyMs=round(
                    (time.monotonic() - request_started) * 1000,
                    3,
                ),
                error=str(exc),
            )
            return JSONResponse(
                openai_error(exc, error_type="server_error", code="transcription_failed"),
                status_code=500,
                headers=response_headers,
            )

    return router
