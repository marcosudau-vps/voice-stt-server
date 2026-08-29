"""AP-SRV-030 - command identity, payload validation and the replay cache.

These are the pure unit tests of the layer that sits *around* the state
machine. The end-to-end proof that a replay really has no second effect on the
gate, the timers and the ledger lives in
``tests/unit/test_server_command_timer_e2e.py``.

AP-SRV-030 C2 additions:

* control commands require a non-empty ``activationId`` (T1);
* control commands are source-neutral: a legacy ``source`` field is neither
  an authorisation nor part of the semantic payload identity (F6);
* a rejected command with a usable ``commandId`` still occupies the replay
  identity, so a later valid command with the same id is a conflict (F3).
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
    prepare_activation_command,
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
                    "activationId": "a-7",
                })
                self.assertEqual(command.action, action)
                self.assertEqual(command.activation_id, "a-7")

    def test_the_deprecated_extend_alias_is_gone(self):
        """AP-SRV-070: ``extend`` is no longer a spelling of ``refresh``.

        The alias survived AP-SRV-030 only so that an AP-SRV-010 client kept
        working. With the legacy cut the v1 parser has one vocabulary again,
        the same four canonical actions v2 has always had, so the spelling is
        an ordinary unknown action rather than a second name for a contract
        action.
        """
        self._rejects(
            {
                "commandId": "c-3",
                "action": "extend",
                "source": "manual",
                "activationId": "a-1",
            },
            "invalid_action",
            "c-3",
        )

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

    def test_control_commands_require_activation_id(self):
        """T1 / F5: ``refresh|finish|cancel`` without activation id is invalid."""
        for action in ("refresh", "finish", "cancel"):
            for payload in (
                {"commandId": "c-t1", "action": action},
                {"commandId": "c-t1", "action": action, "activationId": ""},
                {
                    "commandId": "c-t1",
                    "action": action,
                    "activationId": "   ",
                },
                {
                    "commandId": "c-t1",
                    "action": action,
                    "source": "manual",
                },
            ):
                with self.subTest(action=action, payload=payload):
                    prepared = prepare_activation_command(payload)
                    self.assertIsNone(prepared.command)
                    self.assertEqual(
                        prepared.rejection_reason, "invalid_payload"
                    )
                    self.assertEqual(prepared.command_id, "c-t1")

    def test_control_source_is_not_part_of_semantic_payload_identity(self):
        """F6: a legacy source field must not create a replay conflict."""
        with_source = prepare_activation_command({
            "commandId": "c-6",
            "action": "refresh",
            "source": "manual",
            "activationId": "a-1",
        })
        without_source = prepare_activation_command({
            "commandId": "c-6",
            "action": "refresh",
            "activationId": "a-1",
        })
        another_source = prepare_activation_command({
            "commandId": "c-6",
            "action": "refresh",
            "source": "wake_word",
            "activationId": "a-1",
        })
        self.assertEqual(
            with_source.payload_key, without_source.payload_key
        )
        self.assertEqual(
            with_source.payload_key, another_source.payload_key
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
            "activationId": "a-1",
        }
        original = parse_activation_command(base).payload_key
        for field, value in (
            ("action", "cancel"),
            ("activationId", "a-2"),
        ):
            with self.subTest(field=field):
                changed = dict(base)
                changed[field] = value
                self.assertNotEqual(
                    parse_activation_command(changed).payload_key, original
                )

    # -- AP-SRV-030 C2: replay identity of rejected commands (F3) ------------

    def _prepared(self, payload):
        return prepare_activation_command(payload)

    def test_invalid_action_with_valid_command_id_has_replay_identity(self):
        prepared = self._prepared({
            "commandId": "m-1",
            "action": "teleport",
            "source": "manual",
        })
        self.assertEqual(prepared.command_id, "m-1")
        self.assertEqual(prepared.rejection_reason, "invalid_action")
        self.assertIsNone(prepared.command)
        self.assertTrue(prepared.payload_key)

    def test_same_invalid_payload_has_same_key(self):
        payload = {
            "commandId": "m-2",
            "action": "teleport",
            "source": "manual",
        }
        first = prepare_activation_command(payload)
        second = prepare_activation_command({
            "source": "manual",
            "action": "teleport",
            "commandId": "m-2",
        })
        self.assertEqual(first.payload_key, second.payload_key)

    def test_different_invalid_payload_has_different_key(self):
        teleport = prepare_activation_command({
            "commandId": "m-3", "action": "teleport", "source": "manual",
        })
        other = prepare_activation_command({
            "commandId": "m-3", "action": "activate", "source": "manual",
        })
        self.assertNotEqual(teleport.payload_key, other.payload_key)
        self.assertNotEqual(
            teleport.payload_key,
            prepare_activation_command({
                "commandId": "m-3",
                "action": "teleport",
                "source": "wake_word",
            }).payload_key,
        )

    def test_missing_command_id_has_no_replay_identity(self):
        prepared = prepare_activation_command({
            "action": "activate", "source": "manual",
        })
        self.assertEqual(prepared.command_id, "")
        self.assertEqual(prepared.payload_key, ())
        self.assertEqual(prepared.rejection_reason, "missing_command_id")

    def test_invalid_command_id_has_no_replay_identity(self):
        prepared = prepare_activation_command({
            "commandId": 17, "action": "activate", "source": "manual",
        })
        self.assertEqual(prepared.command_id, "")
        self.assertEqual(prepared.payload_key, ())
        self.assertEqual(prepared.rejection_reason, "invalid_command_id")


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

    def test_a_rejected_command_with_valid_id_occupies_the_identity(self):
        """F3: a usable commandId stays occupied even when the payload rejects."""
        payload = {
            "commandId": "m-1",
            "action": "teleport",
            "source": "manual",
        }
        prepared = prepare_activation_command(payload)
        self.cache.store(
            prepared.command_id, prepared.payload_key, {"reason": "invalid_action"}
        )
        self.assertEqual(
            self.cache.lookup(prepared.command_id, prepared.payload_key).state,
            REPLAY,
        )
        valid = prepare_activation_command({
            "commandId": "m-1", "action": "activate", "source": "manual",
        })
        self.assertEqual(
            self.cache.lookup(valid.command_id, valid.payload_key).state,
            CONFLICT,
        )

    def test_a_keyless_rejection_never_occupies_the_cache(self):
        self.assertEqual(
            self.cache.lookup("", ()).state, MISS
        )

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