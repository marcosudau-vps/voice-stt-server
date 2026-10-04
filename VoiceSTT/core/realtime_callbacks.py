"""
Internal realtime callback publication helpers.
"""

import threading

from .state import run_callback


#: Provenance of the simple realtime text callback currently being dispatched
#: on this thread: ``(recording_id, segment_id)`` frozen before inference, or
#: absent. Lets the session re-validate immediately before publication without
#: changing the public text-only callback signatures.
simple_callback_provenance = threading.local()


def publish_realtime_transcription_stabilized(recorder, text):
    """
    Publishes stabilized realtime text while recording is active.
    """
    if recorder.on_realtime_transcription_stabilized:
        if recorder.is_recording:
            run_callback(recorder, recorder.on_realtime_transcription_stabilized, text)


def publish_realtime_transcription_update(recorder, text):
    """
    Publishes realtime preview text while recording is active.
    """
    if recorder.on_realtime_transcription_update:
        if recorder.is_recording:
            run_callback(recorder, recorder.on_realtime_transcription_update, text)
