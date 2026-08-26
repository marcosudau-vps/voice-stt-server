import threading
import unittest
import queue

from api_fastapi_server.segment_ledger import SegmentLedger, thaw_value
from VoiceSTT.core.recording_buffers import (
    get_next_recorded_audio,
    queue_recorded_audio,
)


class SegmentLedgerTests(unittest.TestCase):
    def setUp(self):
        self.ledger = SegmentLedger(
            "session",
            clock=lambda: 12.5,
            request_id_factory=iter(["job-1", "job-2", "job-3"]).__next__,
        )
        self.assertTrue(self.ledger.open_activation("a-1", 1, {"nested": [1]}))

    def test_context_is_stable_and_sequence_is_session_wide(self):
        first = self.ledger.accept_segment("a-1", 7)
        self.ledger.close_activation("a-1", "finished")
        self.assertTrue(self.ledger.open_activation("a-2", 2, {"language": "de"}))
        second = self.ledger.accept_segment("a-2", 8)

        self.assertEqual(first.request_id, "job-1")
        self.assertEqual((first.segment_sequence, second.segment_sequence), (1, 2))
        self.assertEqual(thaw_value(first.effective_settings), {"nested": [1]})

    def test_out_of_order_results_wait_for_terminal_hole(self):
        first = self.ledger.accept_segment("a-1", 1)
        second = self.ledger.accept_segment("a-1", 2)
        self.ledger.close_activation("a-1", "finished")

        later = self.ledger.resolve_completed(second, "two")
        self.assertEqual(later.publications, ())
        released = self.ledger.resolve_terminal(first, "discarded", "empty_final")

        self.assertEqual([item.text for item in released.publications], ["two"])
        self.assertEqual(released.activation_terminals[0].state, "completed")
        self.assertEqual(self.ledger.snapshot()["pendingSegmentCount"], 0)

    def test_each_non_publication_terminal_releases_later_result(self):
        for state in ("discarded", "cancelled", "failed"):
            with self.subTest(state=state):
                ledger = SegmentLedger("s")
                ledger.open_activation("a", 1)
                first = ledger.accept_segment("a", 1)
                second = ledger.accept_segment("a", 2)
                ledger.close_activation("a", "finished")
                self.assertEqual(ledger.resolve_completed(second, "later").publications, ())
                update = ledger.resolve_terminal(first, state, state)
                self.assertEqual([item.text for item in update.publications], ["later"])

    def test_duplicate_and_concurrent_terminal_callbacks_win_once(self):
        context = self.ledger.accept_segment("a-1", 1)
        self.ledger.close_activation("a-1", "finished")
        changed = []
        barrier = threading.Barrier(3)

        def resolve(state):
            try:
                barrier.wait(timeout=2.0)
                changed.append(
                    self.ledger.resolve_terminal(context, state, state).changed
                )
            except Exception as e:
                changed.append(e)

        threads = [
            threading.Thread(target=resolve, args=("failed",)),
            threading.Thread(target=resolve, args=("cancelled",)),
        ]
        for thread in threads:
            thread.start()
        barrier.wait(timeout=2.0)
        for thread in threads:
            thread.join(timeout=2.0)

        self.assertEqual(sorted(changed), [False, True])
        self.assertEqual(self.ledger.snapshot()["terminalSegmentCount"], 1)

    def test_cancel_suppresses_prepared_but_unpublished_text(self):
        first = self.ledger.accept_segment("a-1", 1)
        second = self.ledger.accept_segment("a-1", 2)
        self.assertEqual(self.ledger.resolve_completed(second, "secret").publications, ())

        cancelled = self.ledger.close_activation(
            "a-1", "client_cancel", requested_terminal="cancelled", cancel_pending=True
        )

        self.assertEqual(cancelled.publications, ())
        self.assertEqual(cancelled.activation_terminals[0].state, "cancelled")
        self.assertFalse(self.ledger.resolve_completed(first, "late").changed)

    def test_cancel_all_marks_every_activation_before_one_session_drain(self):
        ledger = SegmentLedger("session")
        ledger.open_activation("a-1", 1)
        first = ledger.accept_segment("a-1", 1)
        ledger.close_activation("a-1", "finished")
        ledger.open_activation("a-2", 2)
        second = ledger.accept_segment("a-2", 2)
        self.assertEqual(
            ledger.resolve_completed(second, "must-not-leak").publications,
            (),
        )

        cancelled = ledger.cancel_all("session_closed")

        self.assertEqual(cancelled.publications, ())
        self.assertEqual(
            [item.context.segment_sequence for item in cancelled.resolutions],
            [1, 2],
        )
        self.assertEqual(
            [item.state for item in cancelled.resolutions],
            ["cancelled", "cancelled"],
        )
        self.assertEqual(
            [item.state for item in cancelled.activation_terminals],
            ["cancelled", "cancelled"],
        )
        self.assertFalse(ledger.resolve_completed(first, "late").changed)
        self.assertEqual(ledger.snapshot()["pendingSegmentCount"], 0)

    def test_publish_then_cancel_never_retracts_or_republishes(self):
        context = self.ledger.accept_segment("a-1", 1)
        published = self.ledger.resolve_completed(context, "kept")
        self.assertEqual([item.text for item in published.publications], ["kept"])

        cancelled = self.ledger.close_activation(
            "a-1", "client_cancel", requested_terminal="cancelled", cancel_pending=True
        )
        self.assertEqual(cancelled.publications, ())
        self.assertEqual(cancelled.activation_terminals[0].state, "cancelled")
        self.assertFalse(self.ledger.resolve_completed(context, "duplicate").changed)

    def test_empty_activation_terminal_is_emitted_once(self):
        first = self.ledger.close_activation("a-1", "finished")
        duplicate = self.ledger.close_activation("a-1", "finished")

        self.assertEqual(len(first.activation_terminals), 1)
        self.assertEqual(first.activation_terminals[0].accepted_segment_count, 0)
        self.assertEqual(duplicate.activation_terminals, ())
        self.assertFalse(self.ledger.open_activation("a-1", 1))

    def test_audio_queue_carries_the_immutable_segment_context(self):
        context = self.ledger.accept_segment("a-1", 1)
        recorder = type("Recorder", (), {})()
        recorder.recorded_audio_queue = queue.Queue()
        recorder._active_recording_context = context

        queue_recorded_audio(recorder, [b"audio"])
        queued = get_next_recorded_audio(recorder)

        self.assertEqual(queued["segment_context"], context)
        self.assertIsNot(queued["segment_context"], context)

    def test_empty_audio_is_marked_as_not_queued(self):
        recorder = type("Recorder", (), {})()
        recorder.recorded_audio_queue = queue.Queue()

        queue_recorded_audio(recorder, [])

        self.assertFalse(recorder._last_recording_was_queued)
        self.assertTrue(recorder.recorded_audio_queue.empty())


if __name__ == "__main__":
    unittest.main()
