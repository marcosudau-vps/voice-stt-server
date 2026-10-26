"""Shared unit-test isolation.

The native-Kroko guard is deliberately process-wide (it models the native
license singleton). Tests must not inherit a Pro identity, key context or
lease from each other, so every test starts and ends with a clean guard.
"""
import pytest

from VoiceSTT.kroko import native_guard


@pytest.fixture(autouse=True)
def _isolated_kroko_native_guard():
    native_guard.process_guard().reset_for_tests()
    yield
    native_guard.process_guard().reset_for_tests()
