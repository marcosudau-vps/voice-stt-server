"""AP-SRV-030 - command identity, payload validation and the replay cache.

These are the pure unit tests of the layer that sits *around* the state
machine. The end-to-end proof that a replay really has no second effect on the
gate, the timers and the ledger lives in
``tests/unit/test_server_command_timer_e2e.py``.
"""

import threading
import unittest

from api_fastapi_server.activation_commands import (
    ACTIVATION_ACTIONS,
    CONFLICT,
    CommandRejected,
    CommandReplayCache,
    MISS,
    REPLAY,
    parse_activation_command,
)


class ActivationCommandParsingTests(unittest.TestCase):
    def _rejects(self, payload, reason, command_id=""):
        with self.assertRaises(CommandRejected) as caught:
            parse_activation_command(payload)
        self.assertEqual(caught.exception.reason, reason)
        self.assertEqual(caught.exception.command_id, command_id)

    def test_the_four_canonical_actions_are_the_contract_actions(self):
        self.assertEqual(
            ACTIVATION_ACTIONS, ("activate", "refresh", "finish", "cancel")
        )

    def test_an_activate_command_carries_source_and_no_activation_id(self):
        command = parse_activation_command({
            "commandId": "c-1", "action": "activate", "source": "manual",
        })
        self.assertEqual(command.command_id, "c-1")
        self.assertEqual(command.action, "activate")
        self.assertEqual(command.source, "manual")
        self.assertIsNone(command.activation_id)

    def test_a_control_command_keeps_the_observed_activation_id(self):
        for action in ("refresh", "finish", "cancel"):
            with self.subTest(action=action):
                command = parse_activation_command({
                    "commandId": "c-2",
                    "action": action,
                    "source": "manual",
                    "activationId": "a-7",
                })
                self.assertEqual(command.action, action)
                self.assertEqual(command.activation_id, "a-7")

    def test_the_deprecated_extend_alias_normalises_to_refresh(self):
        aliased = parse_activation_command({
            "commandId": "c-3", "action": "extend", "source": "manual",
        })
        canonical = parse_activation_command({
            "commandId": "c-3", "action": "refresh", "source": "manual",
        })
        self.assertEqual(aliased.action, "refresh")
        # The spelling must not turn a replay into a conflict.
        self.assertEqual(aliased.payload_key, canonical.payload_key)

    def test_activate_must_not_address_an_activation(self):
        self._rejects(
            {
                "commandId": "c-4",
                "action": "activate",
                "source": "manual",
                "activationId": "a-1",
            },
            "invalid_payload",
            "c-4",
        )

    def test_every_malformed_payload_has_its_own_reason(self):
        cases = (
            (["trigger"], "invalid_payload", ""),
            ({"action": "activate", "source": "manual"}, "missing_command_id", ""),
            (
                {"commandId": "   ", "action": "activate", "source": "manual"},
                "missing_command_id",
                "",
            ),
            (
                {"commandId": 17, "action": "activate", "source": "manual"},
                "invalid_command_id",
                "",
            ),
            (
                {"commandId": "c-5", "action": "teleport", "source": "manual"},
                "invalid_action",
                "c-5",
            ),
            (
                {"commandId": "c-6", "action": ["activate"], "source": "manual"},
                "invalid_action",
                "c-6",
            ),
            (
                {"commandId": "c-7", "action": "activate", "source": "telepathy"},
                "invalid_source",
                "c-7",
            ),
            (
                {"commandId": "c-8", "action": "activate", "source": 5},
                "invalid_source",
                "c-8",
            ),
            (
                {
                    "commandId": "c-9",
                    "action": "finish",
                    "source": "manual",
                    "activationId": 12,
                },
                "invalid_payload",
                "c-9",
            ),
        )
        for payload, reason, command_id in cases:
            with self.subTest(reason=reason, payload=payload):
                self._rejects(payload, reason, command_id)

    def test_the_payload_key_covers_every_semantic_field(self):
        base = {
            "commandId": "c-10",
            "action": "finish",
            "source": "manual",
            "activationId": "a-1",
        }
        original = parse_activation_command(base).payload_key
        for field, value in (
            ("action", "cancel"),
            ("source", "wake_word"),
            ("activationId", "a-2"),
        ):
            with self.subTest(field=field):
                changed = dict(base)
                changed[field] = value
                self.assertNotEqual(
                    parse_activation_command(changed).payload_key, original
                )


class CommandReplayCacheTests(unittest.TestCase):
    def setUp(self):
        self.cache = CommandReplayCache()

    def test_an_unknown_command_id_is_a_miss(self):
        self.assertEqual(self.cache.lookup("c-1", ("activate",)).state, MISS)

    def test_the_same_payload_returns_the_stored_answer(self):
        self.cache.store("c-1", ("activate",), {"reason": "activated"})
        for _ in range(3):
            lookup = self.cache.lookup("c-1", ("activate",))
            self.assertEqual(lookup.state, REPLAY)
            self.assertEqual(lookup.result, {"reason": "activated"})

    def test_a_different_payload_is_a_conflict(self):
        self.cache.store("c-1", ("activate",), {"reason": "activated"})
        self.assertEqual(self.cache.lookup("c-1", ("cancel",)).state, CONFLICT)
        # The conflict must not replace the original entry.
        self.assertEqual(
            self.cache.lookup("c-1", ("activate",)).result,
            {"reason": "activated"},
        )

    def test_a_stored_entry_is_never_overwritten(self):
        self.cache.store("c-1", ("activate",), {"n": 1})
        self.cache.store("c-1", ("activate",), {"n": 2})
        self.assertEqual(self.cache.lookup("c-1", ("activate",)).result, {"n": 1})

    def test_the_cache_is_not_trimmed_while_the_session_lives(self):
        """The contract requires it to hold for at least the whole session."""
        for index in range(1000):
            self.cache.store(f"c-{index}", ("activate",), {"n": index})
        self.assertEqual(len(self.cache), 1000)
        self.assertEqual(
            self.cache.lookup("c-0", ("activate",)).result, {"n": 0}
        )
        self.cache.clear()
        self.assertEqual(len(self.cache), 0)

    def test_concurrent_first_writers_agree_on_one_answer(self):
        start = threading.Barrier(8)
        stored = []
        lock = threading.Lock()

        def writer(index):
            start.wait(timeout=10)
            self.cache.store("c-race", ("activate",), {"writer": index})
            with lock:
                stored.append(self.cache.lookup("c-race", ("activate",)).result)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        self.assertEqual(len(stored), 8)
        self.assertEqual(len({tuple(sorted(item.items())) for item in stored}), 1)


if __name__ == "__main__":
    unittest.main()
