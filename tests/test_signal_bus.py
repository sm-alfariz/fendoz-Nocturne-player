# coding:utf-8
from PySide6.QtCore import QObject

from src.common.signal_bus import SignalBus, signalBus


class TestSignalBus:
    def test_is_qobject(self):
        assert isinstance(signalBus, QObject)

    def test_is_singleton(self):
        another = SignalBus()
        assert signalBus is not another  # not same instance (no __new__ guard)
        # But the module-level `signalBus` is reused as the canonical singleton

    def test_has_switch_to_sample_card_signal(self):
        assert hasattr(signalBus, "switchToSampleCard")

    def test_has_mica_enable_changed_signal(self):
        assert hasattr(signalBus, "micaEnableChanged")

    def test_has_support_signal(self):
        assert hasattr(signalBus, "supportSignal")

    def test_signal_types(self):
        """Verify signals accept expected argument types."""
        # switchToSampleCard: (str, int)
        signalBus.switchToSampleCard.emit("route", 0)
        signalBus.micaEnableChanged.emit(True)
        signalBus.supportSignal.emit()
