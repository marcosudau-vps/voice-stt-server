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
            request_id_factory=iter(["job-1", "job-2", "job-3", "job-4"]).__next__,
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
            barrier.wait()
            changed.append(
                self.ledger.resolve_terminal(context, state, state).changed
            )

        threads = [
            threading.Thread(target=resolve, args=("failed",)),
            threading.Thread(target=resolve, args=("cancelled",)),
        ]
        for thread in threads:
            thread.start()
        barrier.wait()
        for thread in threads:
            thread.join()

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

    # -- AP-SRV-030 C2: per-activation cancel barrier -------------------------

    def assert_terminal_cardinality(self, ledger=None):
        ledger = ledger or self.ledger
        snapshot = ledger.snapshot()
        self.assertEqual(
            snapshot["acceptedSegmentCount"],
            snapshot["terminalSegmentCount"],
        )

    def test_cancel_request_blocks_later_completed_publication(self):
        ledger = SegmentLedger("session")
        ledger.open_activation("a-1", 1)
        first = ledger.accept_segment("a-1", 1)
        second = ledger.accept_segment("a-1", 2)

        barrier = ledger.mark_cancel_requested("a-1", "cancelled")
        self.assertEqual(barrier.publications, ())

        after = ledger.resolve_completed(second, "late-after-cancel")
        self.assertEqual(after.publications, ())
        self.assertEqual(after.resolutions, ())
        self.assertFalse(after.changed)

        terminal = ledger.resolve_terminal(first, "discarded", "empty_final")
        self.assertEqual(terminal.publications, ())
        self.assert_terminal_cardinality(ledger)

    def test_cancel_request_clears_prepared_but_unpublished_text(self):
        ledger = SegmentLedger("session")
        ledger.open_activation("a-1", 1)
        seg1 = ledger.accept_segment("a-1", 1)
        seg2 = ledger.accept_segment("a-1", 2)

        # Segment 2 completes while segment 1 is still an open hole: its text
        # exists only as prepared_text and must never become visible.
        prepared = ledger.resolve_completed(seg2, "must-not-leak")
        self.assertEqual(prepared.publications, ())

        barrier = ledger.mark_cancel_requested("a-1", "cancelled")
        self.assertEqual(barrier.publications, ())
        cancelled = [
            resolution for resolution in barrier.resolutions
            if resolution.context.segment_sequence == 2
        ]
        self.assertEqual(len(cancelled), 1)
        self.assertEqual(cancelled[0].state, "cancelled")

        # Resolving the hole must not publish the prepared text.
        terminal = ledger.resolve_terminal(seg1, "discarded", "empty_final")
        self.assertEqual(terminal.publications, ())
        self.assertEqual(ledger.snapshot()["pendingSegmentCount"], 0)
        self.assert_terminal_cardinality(ledger)

    def test_cancel_request_rejects_late_segment_acceptance(self):
        ledger = SegmentLedger("session")
        ledger.open_activation("a-1", 1)
        ledger.mark_cancel_requested("a-1", "cancelled")
        with self.assertRaises(RuntimeError):
            ledger.accept_segment("a-1", 99)
        self.assertEqual(ledger.snapshot()["acceptedSegmentCount"], 0)

    def test_cancel_request_does_not_withdraw_already_drained_publication(self):
        ledger = SegmentLedger("session")
        ledger.open_activation("a-1", 1)
        context = ledger.accept_segment("a-1", 1)
        published = ledger.resolve_completed(context, "kept")
        self.assertEqual([item.text for item in published.publications], ["kept"])

        # A second segment is still unprocessed at cancel time.
        pending = ledger.accept_segment("a-1", 2)
        barrier = ledger.mark_cancel_requested("a-1", "cancelled")
        self.assertEqual(barrier.publications, ())
        self.assertEqual(len(barrier.resolutions), 1)
        self.assertEqual(barrier.resolutions[0].context.segment_id, 2)
        self.assertEqual(barrier.resolutions[0].state, "cancelled")
        # The only still-pending segment was cancelled at the barrier.
        self.assertEqual(ledger.snapshot()["pendingSegmentCount"], 0)
        self.assertEqual(ledger.snapshot()["acceptedSegmentCount"], 2)
        # The already drained segment keeps its published text.
        self.assert_terminal_cardinality(ledger)

    def test_close_after_cancel_request_terminalizes_remaining_segments(self):
        ledger = SegmentLedger("session")
        ledger.open_activation("a-1", 1)
        seg1 = ledger.accept_segment("a-1", 1)
        seg2 = ledger.accept_segment("a-1", 2)
        ledger.resolve_completed(seg2, "prepared-not-published")

        barrier = ledger.mark_cancel_requested("a-1", "cancelled")
        self.assertEqual(barrier.publications, ())
        self.assertEqual(len(barrier.resolutions), 2)

        closed = ledger.close_activation(
            "a-1", "cancelled", requested_terminal="cancelled", cancel_pending=True
        )
        self.assertEqual(closed.publications, ())
        self.assertEqual(closed.activation_terminals[0].state, "cancelled")
        snapshot = ledger.snapshot()
        self.assertEqual(snapshot["pendingSegmentCount"], 0)
        self.assert_terminal_cardinality(ledger)

    def test_cancel_request_keeps_sequence_hole_fill_intact(self):
        ledger = SegmentLedger("session")
        ledger.open_activation("a-1", 1)
        seg1 = ledger.accept_segment("a-1", 1)
        seg2 = ledger.accept_segment("a-1", 2)
        self.assertTrue(ledger.open_activation("a-2", 2, {}))
        seg3 = ledger.accept_segment("a-2", 3)
        # a-2 is the newer activation; its prepared text is blocked only by
        # the a-1 hole and becomes visible once that hole closes.
        ledger.resolve_completed(seg3, "later-visible")
        self.assertEqual(
            ledger.resolve_completed(seg2, "hole-waiting").publications, ()
        )

        barrier = ledger.mark_cancel_requested("a-1", "cancel")
        # Only a-1's segments are cancelled.
        self.assertEqual(
            {item.context.activation_id for item in barrier.resolutions},
            {"a-1"},
        )
        # The cancel terminal on seg1 closes the hole, which releases the
        # already prepared a-2 text - that is exactly the reorder drain.
        self.assertEqual(
            [item.text for item in barrier.publications], ["later-visible"]
        )

        terminal = ledger.resolve_terminal(seg1, "discarded", "empty_final")
        self.assertEqual(terminal.publications, ())
        snapshot = ledger.snapshot()
        self.assertEqual(snapshot["acceptedSegmentCount"], 3)
        self.assert_terminal_cardinality(ledger)

    def test_cancel_request_is_idempotent(self):
        ledger = SegmentLedger("session")
        ledger.open_activation("a-1", 1)
        ledger.accept_segment("a-1", 1)

        first = ledger.mark_cancel_requested("a-1", "cancelled")
        second = ledger.mark_cancel_requested("a-1", "cancelled")

        self.assertTrue(first.changed)
        self.assertEqual(len(first.resolutions), 1)
        self.assertEqual(len(second.resolutions), 0)
        self.assertFalse(second.changed)
        snapshot = ledger.snapshot()
        self.assertEqual(snapshot["terminalSegmentCount"], 1)
        self.assert_terminal_cardinality(ledger)
        self.assertEqual(snapshot["nextSegmentSequence"] - 1, 1)

    def test_cancel_request_on_unknown_activation_is_effect_free(self):
        update = self.ledger.mark_cancel_requested("no-such-activation", "cancelled")
        self.assertFalse(update.changed)
        self.assertEqual(update.resolutions, ())
        self.assertEqual(update.publications, ())

    def test_cancel_request_ignores_other_activations(self):
        ledger = SegmentLedger("session")
        ledger.open_activation("a-1", 1)
        ledger.open_activation("a-2", 2)
        own = ledger.accept_segment("a-1", 1)
        other = ledger.accept_segment("a-2", 2)
        self.assertEqual(
            ledger.resolve_completed(other, "other-text").publications, ()
        )

        barrier = ledger.mark_cancel_requested("a-1", "cancelled")
        self.assertEqual(
            {item.context.activation_id for item in barrier.resolutions},
            {"a-1"},
        )
        self.assertEqual(barrier.resolutions[0].state, "cancelled")
        # Only the a-1 hole is cancelled, so the a-2 prepared text is now
        # released by the drain - it is a different activation and unaffected.
        self.assertEqual(
            [item.text for item in barrier.publications], ["other-text"]
        )


if __name__ == "__main__":
    unittest.main()