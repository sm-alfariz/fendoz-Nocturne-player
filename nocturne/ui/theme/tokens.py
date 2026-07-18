# coding:utf-8
"""
tokens.py — Design-token constants (Dark Navy theme).
See 08-design-system.md and mockup-nocturne.html.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Color:
    PRIMARY = "#1E88E5"
    ACCENT = "#4FC3F7"
    BACKGROUND = "#0F172A"
    BACKGROUND_DEEP = "#0A0F1E"
    CARD = "#1E293B"
    CARD_SOFT = "rgba(30,41,59,0.55)"
    BORDER = "rgba(79,195,247,0.14)"
    ACCENT_SECONDARY = "#F472B6"
    TEXT_PRIMARY = "#E2E8F0"
    TEXT_DIM = "#7C8AA5"


@dataclass(frozen=True)
class Spacing:
    SIDEBAR_WIDTH = 220
    LYRICS_PANEL_WIDTH = 300
    CORNER_RADIUS = 18
    TRANSITION_MS = 200


@dataclass(frozen=True)
class Fonts:
    DISPLAY = "Sora"
    BODY = "Inter"
    MONO = "JetBrains Mono"


@dataclass(frozen=True)
class FontWeights:
    LOGO = 800
    DISPLAY_BOLD = 700
    BODY_REGULAR = 400
    BODY_MEDIUM = 500
    BODY_SEMIBOLD = 600
    MONO_REGULAR = 400
    MONO_MEDIUM = 500
