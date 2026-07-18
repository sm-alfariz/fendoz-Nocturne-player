# coding:utf-8
"""
equalizer_view.py — 10-band equalizer UI with presets.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget
from qfluentwidgets import ComboBox, PushButton

from nocturne.core.equalizer import BAND_COUNT, BAND_LABELS, Equalizer
from nocturne.ui.theme.tokens import Color


class BandSlider(QWidget):
    """Single vertical slider for one EQ band."""

    value_changed = Signal(int, float)  # band_index, db_value

    def __init__(self, band_index: int, label: str, parent=None):
        super().__init__(parent)
        self.band_index = band_index
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(4)

        self.slider = QSlider(Qt.Vertical)
        self.slider.setRange(-120, 120)  # -12.0 dB to +12.0 dB (x10)
        self.slider.setValue(0)
        self.slider.setTickPosition(QSlider.TicksBothSides)
        self.slider.valueChanged.connect(self._on_value_changed)
        layout.addWidget(self.slider, 1)

        self.value_label = QLabel("0.0")
        self.value_label.setAlignment(Qt.AlignCenter)
        self.value_label.setStyleSheet(f"color: {Color.TEXT_DIM}; font-size: 10px;")
        layout.addWidget(self.value_label)

        self.band_label = QLabel(label)
        self.band_label.setAlignment(Qt.AlignCenter)
        self.band_label.setStyleSheet(f"color: {Color.TEXT_DIM}; font-size: 11px; font-family: 'JetBrains Mono';")
        layout.addWidget(self.band_label)

    def _on_value_changed(self, val: int) -> None:
        db = val / 10.0
        self.value_label.setText(f"{db:+.1f}")
        self.value_changed.emit(self.band_index, db)

    def set_value(self, db: float) -> None:
        self.slider.setValue(int(db * 10))


class EqualizerView(QWidget):
    """Full equalizer page with sliders + presets."""

    def __init__(self, equalizer: Equalizer, parent=None, assign_callback=None):
        super().__init__(parent)
        self._eq = equalizer
        self._assign_callback = assign_callback
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title
        title = QLabel("Equalizer")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(title)

        # Preset selector
        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel("Preset:"))
        self.preset_combo = ComboBox()
        self.preset_combo.addItems(list(Equalizer.all_presets().keys()))
        self.preset_combo.currentTextChanged.connect(self._on_preset_change)
        preset_row.addWidget(self.preset_combo)
        preset_row.addStretch()

        # Save custom
        self.save_btn = PushButton("Save as custom")
        self.save_btn.clicked.connect(self._save_custom)
        preset_row.addWidget(self.save_btn)

        # Assign to current track
        self.assign_btn = PushButton("Assign to Track")
        self.assign_btn.clicked.connect(self._assign_to_track)
        preset_row.addWidget(self.assign_btn)
        layout.addLayout(preset_row)

        # Sliders
        sliders_row = QHBoxLayout()
        sliders_row.setAlignment(Qt.AlignCenter)
        self._sliders: list[BandSlider] = []
        for i, label in enumerate(BAND_LABELS):
            s = BandSlider(i, f"{label}Hz")
            s.value_changed.connect(self._on_band_changed)
            self._sliders.append(s)
            sliders_row.addWidget(s)
        layout.addLayout(sliders_row)

        layout.addStretch()

    def _on_preset_change(self, name: str) -> None:
        presets = Equalizer.all_presets()
        if name in presets:
            values = presets[name]
            for i, s in enumerate(self._sliders):
                s.set_value(values[i])
            self._eq.apply_preset(name)

    def _on_band_changed(self, index: int, db: float) -> None:
        self._eq.set_band(index, db)
        self.preset_combo.setCurrentText("Custom")

    def _save_custom(self) -> None:
        values = [s.slider.value() / 10.0 for s in self._sliders]
        self._eq.save_custom_preset("Custom", values)

    def _assign_to_track(self) -> None:
        preset = self.preset_combo.currentText()
        if self._assign_callback:
            self._assign_callback(preset)

    def load_for_track(self, eq_preset: str | None) -> None:
        """Set dropdown to the given preset (from track assignment)."""
        if eq_preset and eq_preset in Equalizer.all_presets():
            self.preset_combo.setCurrentText(eq_preset)
