# coding:utf-8
"""
lyrics_panel.py — Right-side lyrics panel with karaoke typing effect.

Matches karaoke style from lirik-generator: per-word highlight using
Enhanced LRC format, rendered via QTextEdit HTML.
"""

from __future__ import annotations

import math
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QLinearGradient, QPainter
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QScrollArea, QTextEdit, QVBoxLayout, QWidget

from nocturne.ui.theme.tokens import Color, Fonts
from nocturne.core.lyrics_sync import LyricLine


class _SyncBadge(QLabel):
    """'SYNCED' badge with pulsing dot animation."""

    def __init__(self, parent=None):
        super().__init__("SYNCED", parent)
        self._pulse = 1.0
        self.setStyleSheet(
            f"color:{Color.ACCENT};font-size:10px;font-family:'{Fonts.MONO}';"
            f"background:rgba(79,195,247,0.1);border:1px solid {Color.BORDER};"
            f"padding:4px 8px;border-radius:8px;"
        )
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._tick_pulse)
        self._timer.start()

    def _tick_pulse(self):
        import time
        self._pulse = 0.5 + 0.5 * math.sin(time.time() * 4.5)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        alpha = int(self._pulse * 255)
        c = QColor(Color.ACCENT)
        c.setAlpha(max(60, alpha))
        glow = QColor(Color.ACCENT)
        glow.setAlpha(max(30, alpha // 3))
        painter.setBrush(glow)
        painter.drawEllipse(7, self.height() // 2 - 4, 8, 8)
        painter.setBrush(c)
        painter.drawEllipse(8, self.height() // 2 - 3, 6, 6)


def _build_lyrics_header() -> QWidget:
    """Build the lyrics panel header with 'Lirik' title and SYNCED badge."""
    h = QWidget()
    h.setStyleSheet(f"border-bottom:1px solid {Color.BORDER};")
    hl = QHBoxLayout(h)
    hl.setContentsMargins(22, 20, 22, 14)
    title = QLabel("Lirik")
    title.setStyleSheet(
        f"font-family:'{Fonts.DISPLAY}';font-size:14px;font-weight:700;color:{Color.TEXT_PRIMARY};"
    )
    hl.addWidget(title)
    hl.addStretch()
    hl.addWidget(_SyncBadge())
    return h


class _WordToken:
    """A single word with its timestamp in ms."""
    __slots__ = ("text", "start_ms", "end_ms")
    def __init__(self, text: str, start_ms: int, end_ms: int) -> None:
        self.text = text
        self.start_ms = start_ms
        self.end_ms = end_ms


class _LineData:
    """One lyric line with per-word timestamps."""
    __slots__ = ("words", "start_ms")
    def __init__(self, words: list[_WordToken]) -> None:
        self.words = words
        self.start_ms = words[0].start_ms if words else 0


def _parse_enhanced_lrc(lines: list[LyricLine]) -> list[_LineData]:
    """Convert standard LyricLine list to enhanced _LineData (word-level).

    If a line contains '<mm:ss.xx>' markers, parses per-word timestamps.
    Otherwise wraps the whole line as one word.
    """
    import re
    result = []
    WORD_RE = re.compile(r"<(\d+):(\d+\.?\d*)>([^<]+)")
    for ll in lines:
        matches = WORD_RE.findall(ll.text)
        if matches:
            words = []
            for m, s, text in matches:
                ts = int(m) * 60000 + int(float(s) * 1000)
                dur = 1000  # default — we'll set end_ms from next word
                words.append(_WordToken(text.strip(), ts, ts + dur))
            # Fix end_ms from next word's start
            for i in range(len(words) - 1):
                words[i].end_ms = words[i + 1].start_ms
            if words:
                result.append(_LineData(words))
        else:
            # Plain line — wrap as single word
            words = [_WordToken(ll.text, ll.timestamp_ms, ll.timestamp_ms + 3000)]
            result.append(_LineData(words))
    return result


class LyricsPanel(QScrollArea):
    """Right-side panel with karaoke typing effect lyrics."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFixedWidth(300)
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setStyleSheet(
            f"background:rgba(15,23,42,0.35);border-left:1px solid {Color.BORDER};"
        )

        self._text_edit = QTextEdit()
        self._text_edit.setReadOnly(True)
        self._text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._text_edit.setStyleSheet(
            "background:transparent;border:none;padding:24px 22px;"
        )
        self._text_edit.viewport().setStyleSheet("background:transparent;")
        self.setWidget(self._text_edit)

        self._lines: list[_LineData] = []
        self._offset_ms = 0
        self._last_active_idx = -1

    def paintEvent(self, event):
        """Draw gradient fade at top and bottom."""
        super().paintEvent(event)
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        fade_height = 40
        w = self.viewport().width()

        top_grad = QLinearGradient(0, 0, 0, fade_height)
        bg = QColor(Color.BACKGROUND)
        bg_t = QColor(bg)
        bg_t.setAlpha(0)
        top_grad.setColorAt(0, bg)
        top_grad.setColorAt(1, bg_t)
        painter.fillRect(0, 0, w, fade_height, top_grad)

        vh = self.viewport().height()
        bot_grad = QLinearGradient(0, vh - fade_height, 0, vh)
        bot_grad.setColorAt(0, bg_t)
        bot_grad.setColorAt(1, bg)
        painter.fillRect(0, vh - fade_height, w, fade_height, bot_grad)

    def _show_placeholder(self, msg: str = "Lirik tidak ditemukan\nuntuk lagu ini") -> None:
        self._lines = []
        self._text_edit.setHtml(
            f"<div style='text-align:center;color:{Color.TEXT_DIM};"
            f"font-size:14px;padding:40px;'>{msg.replace(chr(10), '<br>')}</div>"
        )

    def load_lyrics(self, lines: list[LyricLine]) -> None:
        if not lines:
            self._show_placeholder()
            return
        self._lines = _parse_enhanced_lrc(lines)
        self._text_edit.verticalScrollBar().setValue(0)
        self._last_active_idx = -1
        # Force initial render
        self.highlight_line(-10000)

    def set_offset(self, offset_ms: int) -> None:
        self._offset_ms = offset_ms

    def highlight_line(self, timestamp_ms: int) -> None:
        if not self._lines:
            return

        ts = max(0, timestamp_ms + self._offset_ms)
        active_idx = -1
        for i, ld in enumerate(self._lines):
            if ld.start_ms <= ts:
                active_idx = i
            else:
                break

        if active_idx < 0:
            # Before first line — show dim all
            self._render_all(active_idx, ts)
            return

        self._render_all(active_idx, ts)

        # Auto-scroll active line to centre
        if active_idx != self._last_active_idx:
            self._last_active_idx = active_idx
            # Estimate scroll position: each line ~52px
            target_y = max(0, active_idx * 52 - self.height() // 3)
            self._text_edit.verticalScrollBar().setValue(target_y)

    def _render_all(self, active_idx: int, ts: int) -> None:
        """Build full HTML with karaoke typing effect."""
        parts = [
            "<div style='text-align:center;font-family:sans-serif;'>"
        ]
        n = len(self._lines)
        # Show window: 2 before, active, 2 after
        lo = max(0, active_idx - 2)
        hi = min(n, active_idx + 3)

        for i in range(lo, hi):
            ld = self._lines[i]
            if i < active_idx:
                # Past lines — dim gray
                full = "".join(w.text for w in ld.words)
                parts.append(
                    f"<p style='color:#555;font-size:15px;margin:6px 0;'>{_escape(full)}</p>"
                )
            elif i > active_idx:
                # Future lines — dim white
                full = "".join(w.text for w in ld.words)
                parts.append(
                    f"<p style='color:#AAA;font-size:16px;margin:6px 0;'>{_escape(full)}</p>"
                )
            else:
                # ACTIVE LINE — karaoke typing effect
                parts.append(
                    "<p style='font-size:22px;font-weight:bold;margin:10px 0;'>"
                )
                for w in ld.words:
                    if ts < w.start_ms:
                        # Not yet sung
                        parts.append(
                            f"<span style='color:#555;'>{_escape(w.text)}</span>"
                        )
                    elif ts >= w.end_ms:
                        # Already sung — full accent
                        parts.append(
                            f"<span style='color:{Color.ACCENT};'>{_escape(w.text)}</span>"
                        )
                    else:
                        # Currently singing — typing effect
                        elapsed = ts - w.start_ms
                        dur = w.end_ms - w.start_ms
                        ratio = max(0.0, min(1.0, elapsed / dur)) if dur > 0 else 1.0
                        n_highlight = int(ratio * len(w.text))
                        done = _escape(w.text[:n_highlight])
                        remain = _escape(w.text[n_highlight:])
                        parts.append(
                            f"<span style='color:{Color.ACCENT};'>{done}</span>"
                            f"<span style='color:#555;'>{remain}</span>"
                        )
                parts.append("</p>")

        parts.append("</div>")
        self._text_edit.setHtml("".join(parts))


def _escape(text: str) -> str:
    """HTML-escape text for safe setHtml()."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )
