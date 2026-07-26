if __name__ == '__main__':

    from pathlib import Path
    import sys

    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from RealtimeTTS import TextToAudioStream, EdgeEngine, SystemEngine
    from VoiceSTT import AudioToTextRecorder

    from PyQt5.QtCore import Qt, QTimer, QEvent, pyqtSignal, QThread
    from PyQt5.QtGui import QColor, QPainter, QFontMetrics, QFont, QMouseEvent
    from PyQt5.QtWidgets import QApplication, QWidget, QDesktopWidget, QMenu, QAction

    import logging
    import os
    import time
    import sounddevice as sd
    import numpy as np
    import wavio
    import keyboard

    from app_talk_with_llm.custom_api_chat_endpoint import stream_chat_completion
    from example_app_config import (
        asset_path,
        build_config,
        configure_file_logging,
    )

    config = build_config()
    if "--check" in sys.argv:
        print(
            "Voice assistant dependencies and config are valid "
            f"(final={config.final_backend.name}, "
            f"realtime={config.realtime_backend.name}, language={config.language})."
        )
        raise SystemExit(0)

    app_logger, log_file_path = configure_file_logging(config.logs_dir)
    app_logger.info("Example app starting; log_file=%s", log_file_path)
    max_history_messages = config.max_history_messages
    return_to_wakewords_after_silence = config.return_to_wakewords_after_silence
    start_with_wakeword = config.start_with_wakeword
    start_engine = config.start_engine
    edge_voice_string = config.edge_voice_string
    selected_backend = config.final_backend.name
    selected_realtime_backend = config.realtime_backend.name
    download_root = config.download_root
    recorder_device = config.device
    recorder_compute_type = config.compute_type
    input_device_index = config.input_device_index
    gpu_device_index = config.gpu_device_index
    use_microphone = config.use_microphone
    spinner = config.spinner
    batch_size = config.batch_size
    realtime_batch_size = config.realtime_batch_size
    beam_size = config.beam_size
    beam_size_realtime = config.beam_size_realtime
    initial_prompt = config.initial_prompt
    initial_prompt_realtime = config.initial_prompt_realtime
    suppress_tokens = config.suppress_tokens
    ensure_sentence_starting_uppercase = config.ensure_sentence_starting_uppercase
    ensure_sentence_ends_with_period = config.ensure_sentence_ends_with_period
    print_transcription_time = config.print_transcription_time
    early_transcription_on_silence = config.early_transcription_on_silence
    no_log_file = config.no_log_file
    recorder_log_level = config.log_level
    use_extended_logging = config.use_extended_logging
    faster_whisper_vad_filter = config.faster_whisper_vad_filter
    normalize_audio = config.normalize_audio
    start_callback_in_new_thread = config.start_callback_in_new_thread
    allowed_latency_limit = config.allowed_latency_limit
    sample_rate = config.sample_rate
    buffer_size = config.buffer_size
    handle_buffer_overflow = config.handle_buffer_overflow
    debug_mode = config.debug_mode
    wakeword_backend = config.wakeword_backend
    openwakeword_model_paths = config.openwakeword_model_paths
    openwakeword_inference_framework = config.openwakeword_inference_framework
    wake_words = config.wake_words
    wake_words_sensitivity = config.wake_words_sensitivity
    wake_word_activation_delay = config.wake_word_activation_delay
    wake_word_timeout = config.wake_word_timeout
    wake_word_buffer_duration = config.wake_word_buffer_duration
    silero_sensitivity = config.silero_sensitivity
    silero_use_onnx = config.silero_use_onnx
    silero_deactivity_detection = config.silero_deactivity_detection
    silero_backend = config.silero_backend
    silero_onnx_model_path = config.silero_onnx_model_path
    silero_onnx_threads = config.silero_onnx_threads
    deactivity_silence_confirmation_duration = config.deactivity_silence_confirmation_duration
    webrtc_sensitivity = config.webrtc_sensitivity
    warmup_vad = config.warmup_vad
    post_speech_silence_duration = config.post_speech_silence_duration
    min_length_of_recording = config.min_length_of_recording
    min_gap_between_recordings = config.min_gap_between_recordings
    pre_recording_buffer_duration = config.pre_recording_buffer_duration
    pre_recording_buffer_trim_config = config.pre_recording_buffer_trim_config
    use_main_model_for_realtime = config.use_main_model_for_realtime
    realtime_processing_pause = config.realtime_processing_pause
    init_realtime_after_seconds = config.init_realtime_after_seconds
    enable_realtime_transcription = config.enable_realtime_transcription
    realtime_callback = config.realtime_callback
    realtime_transcription_use_syllable_boundaries = config.realtime_transcription_use_syllable_boundaries
    realtime_boundary_detector_sensitivity = config.realtime_boundary_detector_sensitivity
    realtime_boundary_followup_delays = config.realtime_boundary_followup_delays
    clear_text_delay_ms = config.clear_text_delay_ms
    tts_minimum_sentence_length = config.tts_minimum_sentence_length
    tts_buffer_threshold_seconds = config.tts_buffer_threshold_seconds
    tts_log_characters = config.tts_log_characters
    edge_rate = config.edge_rate
    edge_pitch = config.edge_pitch
    language = config.language
    chat_model = config.chat_model

    user_font_size = config.user_font_size
    user_color = QColor(*config.user_color_rgb)

    assistant_font_size = config.assistant_font_size
    assistant_color = QColor(*config.assistant_color_rgb)




    voice_system = config.voice_system
    system_prompt = config.system_prompt

    print ("Click the top right corner to change the engine")
    print ("Press ESC to stop the current playback")

    system_prompt_message = {
        'role': 'system',
        'content': system_prompt
    }

    MAX_WINDOW_WIDTH = config.max_window_width
    MAX_WIDTH_ASSISTANT = config.max_width_assistant
    MAX_WIDTH_USER = config.max_width_user
    history = []

    recorder_model = config.final_backend.model
    realtime_recorder_model = config.realtime_backend.model
    transcription_engine_options = config.final_backend.options
    realtime_transcription_engine_options = config.realtime_backend.options

    print(f"Using STT backend: {selected_backend}")
    print(f"Using realtime STT backend: {selected_realtime_backend}")
    app_logger.info(
        "Configuration loaded: stt_backend=%s realtime_backend=%s model=%s realtime_model=%s "
        "language=%s start_with_wakeword=%s wake_words=%s return_to_wakewords_after_silence=%.2f "
        "wake_word_timeout=%.2f post_speech_silence_duration=%.2f min_length_of_recording=%.2f "
        "min_gap_between_recordings=%.2f pre_recording_buffer_duration=%.2f "
        "realtime_processing_pause=%.2f init_realtime_after_seconds=%.2f "
        "allowed_latency_limit=%s device=%s compute_type=%s wakeword_backend=%s "
        "wake_word_activation_delay=%.2f wake_word_buffer_duration=%.2f",
        selected_backend,
        selected_realtime_backend,
        recorder_model,
        realtime_recorder_model,
        language,
        start_with_wakeword,
        wake_words,
        return_to_wakewords_after_silence,
        wake_word_timeout,
        post_speech_silence_duration,
        min_length_of_recording,
        min_gap_between_recordings,
        pre_recording_buffer_duration,
        realtime_processing_pause,
        init_realtime_after_seconds,
        allowed_latency_limit,
        recorder_device,
        recorder_compute_type,
        wakeword_backend,
        wake_word_activation_delay,
        wake_word_buffer_duration,
    )

    def generate_response(messages):
        """Generate assistant's response using an OpenAI-compatible endpoint."""
        app_logger.info("Chat completion requested; messages=%d model=%s", len(messages), chat_model)
        yield from stream_chat_completion(
            messages,
            model=chat_model,
            logit_bias={35309: -100, 36661: -100},
        )

    class AudioPlayer(QThread):
        def __init__(self, file_path):
            super(AudioPlayer, self).__init__()
            self.file_path = file_path

        def run(self):
            try:
                wav = wavio.read(self.file_path)
                sound = wav.data.astype(np.float32) / np.iinfo(np.int16).max
                sd.play(sound, wav.rate)
                sd.wait()
            except Exception as exc:
                app_logger.warning("Audio cue playback failed for %s: %s", self.file_path, exc)

    class TextRetrievalThread(QThread):
        textRetrieved = pyqtSignal(str)

        def __init__(self, recorder):
            super().__init__()
            self.recorder = recorder
            self.active = False  
            self.running = True

        def run(self):
            while self.running:
                if self.active:
                    try:
                        app_logger.info("Waiting for final transcription text")
                        text = self.recorder.text()
                    except Exception as exc:
                        app_logger.exception("Text retrieval failed: %s", exc)
                    else:
                        self.recorder.wake_word_activation_delay = return_to_wakewords_after_silence
                        app_logger.info(
                            "Final transcription retrieved; chars=%d wake_word_activation_delay=%.2f",
                            len(text or ""),
                            self.recorder.wake_word_activation_delay,
                        )
                        self.textRetrieved.emit(text)
                    self.active = False
                time.sleep(0.1)

        def activate(self):
            if not self.running:
                return
            if not self.active:
                app_logger.info("Text retrieval activated")
            self.active = True

        def stop(self):
            app_logger.info("Text retrieval stopping")
            self.active = False
            self.running = False

    class TransparentWindow(QWidget):
        updateUI = pyqtSignal()
        clearAssistantTextSignal = pyqtSignal()
        clearUserTextSignal = pyqtSignal()

        def __init__(self):
            super().__init__()

            self.setGeometry(1, 1, 1, 1) 

            self.setWindowTitle("Transparent Window")
            self.setAttribute(Qt.WA_TranslucentBackground)
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)

            self.big_symbol_font = QFont('Arial', 32)
            self.small_symbol_font = QFont('Arial', 17)
            self.user_font = QFont('Arial', user_font_size)
            self.assistant_font = QFont('Arial', assistant_font_size)      
            self.assistant_font.setItalic(True) 

            self.big_symbol_text = ""
            self.small_symbol_text = ""
            self.user_text = ""
            self.assistant_text = ""
            self.displayed_user_text = ""
            self.displayed_assistant_text = ""
            self.stream = None
            self.recorder = None
            self.text_retrieval_thread = None
            self.is_closing = False
            self.last_realtime_log_time = 0
            self.last_realtime_text = ""

            self.user_text_timer = QTimer(self)
            self.assistant_text_timer = QTimer(self)
            self.user_text_timer.timeout.connect(self.clear_user_text)
            self.assistant_text_timer.timeout.connect(self.clear_assistant_text)

            self.clearUserTextSignal.connect(self.init_clear_user_text)
            self.clearAssistantTextSignal.connect(self.init_clear_assistant_text)
            self.user_text_opacity = 255 
            self.assistant_text_opacity = 255 
            self.updateUI.connect(self.update_self)
            self.audio_player = None

            self.run_fade_user = False
            self.run_fade_assistant = False

            self.menu = QMenu()
            self.menu.setStyleSheet("""
                QMenu {
                    background-color: black;
                    color: white;
                    border-radius: 10px;
                }
                QMenu::item:selected {
                    background-color: #555555;
                }
                """)

            self.edge_action = QAction("Edge", self)
            self.system_action = QAction("System", self)
            self.quit_action = QAction("Quit", self)

            self.menu.addAction(self.edge_action)
            self.menu.addAction(self.system_action)
            self.menu.addSeparator() 
            self.menu.addAction(self.quit_action)

            self.edge_action.triggered.connect(lambda: self.select_engine("Edge"))
            self.system_action.triggered.connect(lambda: self.select_engine("System"))
            self.quit_action.triggered.connect(self.close_application)

        def mousePressEvent(self, event: QMouseEvent):
            if event.button() == Qt.LeftButton:
                if event.pos().x() >= self.width() - 100 and event.pos().y() <= 100:
                    self.menu.exec_(self.mapToGlobal(event.pos()))        

        def close_application(self):
            app_logger.info("Close requested from menu")
            self.shutdown_runtime()
            QApplication.quit()

        def shutdown_runtime(self):
            if self.is_closing:
                return
            self.is_closing = True
            app_logger.info("Runtime shutdown started")
            if self.recorder:
                self.recorder.shutdown()
            if self.text_retrieval_thread:
                self.text_retrieval_thread.stop()
                self.text_retrieval_thread.wait(2000)
            keyboard.unhook_all()
            app_logger.info("Runtime shutdown finished")

        def close_application_old(self):
            if self.recorder:
                self.recorder.shutdown()                    
            QApplication.quit()                

        def init(self):

            app_logger.info("Window initialization started")
            self.select_engine(start_engine)

            # recorder = AudioToTextRecorder(spinner=False, model="large_turbo", language="de", on_recording_start=recording_start, silero_sensitivity=0.4, post_speech_silence_duration=0.4, min_length_of_recording=0.3, min_gap_between_recordings=0.01, realtime_preview_resolution = 0.01, realtime_preview = True, realtime_preview_model = "small", on_realtime_preview=text_detected)

            self.recorder = AudioToTextRecorder(
                model=recorder_model,
                transcription_engine=selected_backend,
                transcription_engine_options=transcription_engine_options,
                download_root=download_root,
                device=recorder_device,
                compute_type=recorder_compute_type,
                input_device_index=input_device_index,
                gpu_device_index=gpu_device_index,
                language=language,
                use_microphone=use_microphone,
                spinner=spinner,
                batch_size=batch_size,
                realtime_batch_size=realtime_batch_size,
                beam_size=beam_size,
                beam_size_realtime=beam_size_realtime,
                initial_prompt=initial_prompt,
                initial_prompt_realtime=initial_prompt_realtime,
                suppress_tokens=suppress_tokens,
                ensure_sentence_starting_uppercase=ensure_sentence_starting_uppercase,
                ensure_sentence_ends_with_period=ensure_sentence_ends_with_period,
                print_transcription_time=print_transcription_time,
                early_transcription_on_silence=early_transcription_on_silence,
                wake_words=wake_words,
                wakeword_backend=wakeword_backend,
                openwakeword_model_paths=openwakeword_model_paths,
                openwakeword_inference_framework=openwakeword_inference_framework,
                wake_words_sensitivity=wake_words_sensitivity,
                wake_word_activation_delay=wake_word_activation_delay,
                wake_word_timeout=wake_word_timeout,
                wake_word_buffer_duration=wake_word_buffer_duration,
                silero_use_onnx=silero_use_onnx,
                silero_sensitivity=silero_sensitivity,
                silero_deactivity_detection=silero_deactivity_detection,
                silero_backend=silero_backend,
                silero_onnx_model_path=silero_onnx_model_path,
                silero_onnx_threads=silero_onnx_threads,
                deactivity_silence_confirmation_duration=deactivity_silence_confirmation_duration,
                webrtc_sensitivity=webrtc_sensitivity,
                warmup_vad=warmup_vad,
                on_recording_start=self.on_recording_start,
                on_vad_detect_start=self.on_vad_detect_start,
                on_wakeword_detection_start=self.on_wakeword_detection_start,
                on_transcription_start=self.on_transcription_start,
                post_speech_silence_duration=post_speech_silence_duration,
                min_length_of_recording=min_length_of_recording,
                min_gap_between_recordings=min_gap_between_recordings,
                pre_recording_buffer_duration=pre_recording_buffer_duration,
                pre_recording_buffer_trim_config=pre_recording_buffer_trim_config,
                enable_realtime_transcription=enable_realtime_transcription,
                use_main_model_for_realtime=use_main_model_for_realtime,
                realtime_transcription_engine=selected_realtime_backend,
                realtime_transcription_engine_options=realtime_transcription_engine_options,
                realtime_processing_pause=realtime_processing_pause,
                init_realtime_after_seconds=init_realtime_after_seconds,
                realtime_model_type=realtime_recorder_model,
                realtime_transcription_use_syllable_boundaries=realtime_transcription_use_syllable_boundaries,
                realtime_boundary_detector_sensitivity=realtime_boundary_detector_sensitivity,
                realtime_boundary_followup_delays=realtime_boundary_followup_delays,
                allowed_latency_limit=allowed_latency_limit,
                sample_rate=sample_rate,
                buffer_size=buffer_size,
                handle_buffer_overflow=handle_buffer_overflow,
                debug_mode=debug_mode,
                on_realtime_transcription_update=(
                    self.text_detected
                    if realtime_callback in ("update", "both")
                    else None
                ),
                on_realtime_transcription_stabilized=(
                    self.text_detected
                    if realtime_callback in ("stabilized", "both")
                    else None
                ),
                no_log_file=no_log_file,
                level=recorder_log_level,
                use_extended_logging=use_extended_logging,
                faster_whisper_vad_filter=faster_whisper_vad_filter,
                normalize_audio=normalize_audio,
                start_callback_in_new_thread=start_callback_in_new_thread,
            )
            if not start_with_wakeword:
                self.recorder.wake_word_activation_delay = return_to_wakewords_after_silence
                app_logger.info(
                    "Start mode skips wake word; wake_word_activation_delay=%.2f",
                    self.recorder.wake_word_activation_delay,
                )
                
            self.text_retrieval_thread = TextRetrievalThread(self.recorder)
            self.text_retrieval_thread.textRetrieved.connect(self.process_user_text)
            self.text_retrieval_thread.start()
            self.text_retrieval_thread.activate()

            try:
                keyboard.on_press_key('esc', self.on_escape)
            except Exception as exc:
                app_logger.warning("ESC keyboard hook could not be registered: %s", exc)
            app_logger.info("Window initialization finished")

        def closeEvent(self, event):
            self.shutdown_runtime()
            event.accept()

        def select_engine(self, engine_name):
            if self.stream:
                app_logger.info("Stopping current TTS stream before engine switch")
                self.stream.stop()
                self.stream = None

            engine = None

            if engine_name == "Edge":
                engine = EdgeEngine(
                        rate=edge_rate,
                        pitch=edge_pitch,
                    )
                voice_edge= edge_voice_string # engine.get_voice(edge_voice_string)
                engine.set_voice(voice_edge)
            else:
                engine = SystemEngine(
                    voice=voice_system,
                    #print_installed_voices=True
                )

            self.stream = TextToAudioStream(
                engine,
                on_character=self.on_character,
                on_text_stream_stop=self.on_text_stream_stop,
                on_text_stream_start=self.on_text_stream_start,
                on_audio_stream_stop=self.on_audio_stream_stop,
                log_characters=tts_log_characters
            )
            sys.stdout.write('\033[K')  # Clear to the end of line
            sys.stdout.write('\r')  # Move the cursor to the beginning of the line
            print (f"Using {engine_name} engine")
            app_logger.info("TTS engine selected: %s", engine_name)


        def text_detected(self, text):
            self.run_fade_user = False
            if self.user_text_timer.isActive():
                self.user_text_timer.stop()
            self.user_text_opacity = 255 
            self.user_text = text
            self.updateUI.emit()
            now = time.time()
            if text != self.last_realtime_text and now - self.last_realtime_log_time >= 1:
                app_logger.info("Realtime transcription update; chars=%d", len(text or ""))
                self.last_realtime_log_time = now
                self.last_realtime_text = text

        def on_escape(self, e):
            if self.stream and self.stream.is_playing():
                app_logger.info("ESC pressed; stopping TTS playback")
                self.stream.stop()

        def showEvent(self, event: QEvent):
            super().showEvent(event)
            if event.type() == QEvent.Show:
                self.set_symbols("⌛", "🚀")
                QTimer.singleShot(1000, self.init) 

        def on_character(self, char):
            if self.stream:
                self.assistant_text += char
                self.updateUI.emit()

        def on_text_stream_stop(self):
            print("\"", end="", flush=True)
            if self.stream:
                assistant_response = self.stream.text()            
                self.assistant_text = assistant_response
                history.append({'role': 'assistant', 'content': assistant_response})
                app_logger.info(
                    "Assistant text stream stopped; chars=%d history_messages=%d",
                    len(assistant_response or ""),
                    len(history),
                )

        def on_audio_stream_stop(self):
            self.set_symbols("🎙️", "⚪")

            if self.stream and self.text_retrieval_thread:
                self.clearAssistantTextSignal.emit()
                self.text_retrieval_thread.activate()
            app_logger.info("Assistant audio stream stopped")

        def generate_answer(self):
            self.run_fade_assistant = False
            if self.assistant_text_timer.isActive():
                self.assistant_text_timer.stop()

            history.append({'role': 'user', 'content': self.user_text})
            self.remove_assistant_text()
            assistant_response = generate_response([system_prompt_message] + history[-max_history_messages:])
            self.stream.feed(assistant_response)
            app_logger.info(
                "Assistant generation started; user_chars=%d history_messages=%d",
                len(self.user_text or ""),
                len(history),
            )
            self.stream.play_async(
                minimum_sentence_length=tts_minimum_sentence_length,
                buffer_threshold_seconds=tts_buffer_threshold_seconds,
            )

        def set_symbols(self, big_symbol, small_symbol):
            self.big_symbol_text = big_symbol
            self.small_symbol_text = small_symbol
            self.updateUI.emit()

        def on_text_stream_start(self):
            self.set_symbols("⌛", "👄")
            app_logger.info("Assistant text stream started")

        def process_user_text(self, user_text):
            user_text = user_text.strip()
            if user_text:
                self.run_fade_user = False
                if self.user_text_timer.isActive():
                    self.user_text_timer.stop()

                self.user_text_opacity = 255 
                self.user_text = user_text
                self.clearUserTextSignal.emit()
                print (f"Me: \"{user_text}\"\nAI: \"", end="", flush=True)
                self.set_symbols("⌛", "🧠")
                app_logger.info("User text accepted; chars=%d", len(user_text))
                QTimer.singleShot(100, self.generate_answer)
            else:
                app_logger.info("Empty transcription ignored")

        def on_transcription_start(self, audio_data=None):
            self.set_symbols("⌛", "📝")
            audio_len = len(audio_data) if audio_data is not None else 0
            app_logger.info("Final transcription started; audio_samples=%d", audio_len)
            return False

        def on_recording_start(self):
            self.text_storage = []
            self.ongoing_sentence = ""
            self.set_symbols("🎙️", "🔴")
            app_logger.info("Recording started")

        def on_vad_detect_start(self):
            if self.small_symbol_text == "💤" or self.small_symbol_text == "🚀":
                self.audio_player = AudioPlayer(asset_path("active.wav"))
                self.audio_player.start() 

            self.set_symbols("🎙️", "⚪")
            app_logger.info("Voice activity listening started")

        def on_wakeword_detection_start(self):
            self.audio_player = AudioPlayer(asset_path("inactive.wav"))
            self.audio_player.start()         

            self.set_symbols("", "💤")
            app_logger.info("Wake-word detection started")

        def init_clear_user_text(self):
            if self.user_text_timer.isActive():
                self.user_text_timer.stop()        
            self.user_text_timer.start(clear_text_delay_ms)

        def remove_user_text(self):
            self.user_text = ""
            self.user_text_opacity = 255 
            self.updateUI.emit()

        def fade_out_user_text(self):
            if not self.run_fade_user:
                return

            if self.user_text_opacity > 0:
                self.user_text_opacity -= 5 
                self.updateUI.emit()
                QTimer.singleShot(50, self.fade_out_user_text)
            else:
                self.run_fade_user = False
                self.remove_user_text()        

        def clear_user_text(self):
            self.user_text_timer.stop()

            if not self.user_text:
                return

            self.user_text_opacity = 255
            self.run_fade_user = True
            self.fade_out_user_text()

        def init_clear_assistant_text(self):
            if self.assistant_text_timer.isActive():
                self.assistant_text_timer.stop()        
            self.assistant_text_timer.start(clear_text_delay_ms)

        def remove_assistant_text(self):
            self.assistant_text = ""
            self.assistant_text_opacity = 255 
            self.updateUI.emit()

        def fade_out_assistant_text(self):
            if not self.run_fade_assistant:
                return
            
            if self.assistant_text_opacity > 0:
                self.assistant_text_opacity -= 5 
                self.updateUI.emit()
                QTimer.singleShot(50, self.fade_out_assistant_text)
            else:
                self.run_fade_assistant = False
                self.remove_assistant_text()        

        def clear_assistant_text(self):
            self.assistant_text_timer.stop()

            if not self.assistant_text:
                return

            self.assistant_text_opacity = 255
            self.run_fade_assistant = True
            self.fade_out_assistant_text()

        def update_self(self):

            self.blockSignals(True)
                    
            self.displayed_user_text, self.user_width = self.return_text_adjusted_to_width(self.user_text, self.user_font, MAX_WIDTH_USER)
            self.displayed_assistant_text, self.assistant_width = self.return_text_adjusted_to_width(self.assistant_text, self.assistant_font, MAX_WIDTH_ASSISTANT)       

            fm_symbol = QFontMetrics(self.big_symbol_font)
            self.symbol_width = fm_symbol.width(self.big_symbol_text) + 3
            self.symbol_height = fm_symbol.height() + 8

            self.total_width = MAX_WINDOW_WIDTH

            fm_user = QFontMetrics(self.user_font)
            user_text_lines = (self.displayed_user_text.count("\n") + 1)
            self.user_height = fm_user.height() * user_text_lines + 7

            fm_assistant = QFontMetrics(self.assistant_font)
            assistant_text_lines = (self.displayed_assistant_text.count("\n") + 1)
            self.assistant_height = fm_assistant.height() * assistant_text_lines + 18

            self.total_height = sum([self.symbol_height, self.user_height, self.assistant_height])

            desktop = QDesktopWidget()
            screen_rect = desktop.availableGeometry(desktop.primaryScreen())
            self.setGeometry(screen_rect.right() - self.total_width - 50, 0, self.total_width + 50, self.total_height + 50)

            self.blockSignals(False)

            self.update()

        def drawTextWithOutline(self, painter, x, y, width, height, alignment, text, textColor, outlineColor, outline_size):
            painter.setPen(outlineColor)
            for dx, dy in [(-outline_size, 0), (outline_size, 0), (0, -outline_size), (0, outline_size),
                        (-outline_size, -outline_size), (outline_size, -outline_size),
                        (-outline_size, outline_size), (outline_size, outline_size)]:
                painter.drawText(x + dx, y + dy, width, height, alignment, text)

            painter.setPen(textColor)
            painter.drawText(x, y, width, height, alignment, text)

        def paintEvent(self, event):
            painter = QPainter(self)

            offsetX = 4
            offsetY = 5
        
            painter.setPen(QColor(255, 255, 255))

            # Draw symbol
            painter.setFont(self.big_symbol_font)
            if self.big_symbol_text:
                painter.drawText(self.total_width - self.symbol_width + 5 + offsetX, offsetY, self.symbol_width, self.symbol_height, Qt.AlignRight | Qt.AlignTop, self.big_symbol_text)
                painter.setFont(self.small_symbol_font)
                painter.drawText(self.total_width - self.symbol_width + 17 + offsetX, offsetY + 10, self.symbol_width, self.symbol_height, Qt.AlignRight | Qt.AlignBottom, self.small_symbol_text)
            else:
                painter.setFont(self.small_symbol_font)
                painter.drawText(self.total_width - 43 + offsetX, offsetY + 2, 50, 50, Qt.AlignRight | Qt.AlignBottom, self.small_symbol_text)

            # Draw User Text
            painter.setFont(self.user_font)
            user_x = self.total_width - self.user_width - 45 + offsetX
            user_y = offsetY + 15
            user_color_with_opacity = QColor(user_color.red(), user_color.green(), user_color.blue(), self.user_text_opacity)
            outline_color_with_opacity = QColor(0, 0, 0, self.user_text_opacity)
            self.drawTextWithOutline(painter, user_x, user_y, self.user_width, self.user_height, Qt.AlignRight | Qt.AlignTop, self.displayed_user_text, user_color_with_opacity, outline_color_with_opacity, 2)

            # Draw Assistant Text
            painter.setFont(self.assistant_font)
            assistant_x = self.total_width - self.assistant_width - 5  + offsetX
            assistant_y = self.user_height + offsetY + 15
            assistant_color_with_opacity = QColor(assistant_color.red(), assistant_color.green(), assistant_color.blue(), self.assistant_text_opacity)
            outline_color_with_opacity = QColor(0, 0, 0, self.assistant_text_opacity)
            self.drawTextWithOutline(painter, assistant_x, assistant_y, self.assistant_width, self.assistant_height, Qt.AlignRight | Qt.AlignTop, self.displayed_assistant_text, assistant_color_with_opacity, outline_color_with_opacity, 2)

        def return_text_adjusted_to_width(self, text, font, max_width_allowed):
            """
            Line feeds are inserted so that the text width does never exceed max_width.
            Text is only broken up on whole words.
            """
            fm = QFontMetrics(font)
            words = text.split(' ')
            adjusted_text = ''
            current_line = ''
            max_width_used = 0
            
            for word in words:
                current_width = fm.width(current_line + word)
                if current_width <= max_width_allowed:
                    current_line += word + ' '
                else:
                    line_width = fm.width(current_line)
                    if line_width > max_width_used:
                        max_width_used = line_width
                    adjusted_text += current_line + '\n'
                    current_line = word + ' '
            
            line_width = fm.width(current_line)
            if line_width > max_width_used:
                max_width_used = line_width
            adjusted_text += current_line 
            return adjusted_text.rstrip(), max_width_used         

    app = QApplication(sys.argv)

    window = TransparentWindow()
    window.show()
    auto_quit_ms = os.environ.get("EXAMPLE_APP_AUTO_QUIT_MS")
    if auto_quit_ms:
        def auto_quit_application():
            app_logger.info("Auto quit requested after %s ms", auto_quit_ms)
            window.shutdown_runtime()
            QApplication.exit(0)

        QTimer.singleShot(int(auto_quit_ms), auto_quit_application)

    exit_code = app.exec_()
    app_logger.info("Example app exited; exit_code=%s", exit_code)
    sys.exit(0 if auto_quit_ms else exit_code)
