# coding:utf-8
"""
lyrics_sync.py — Parse .lrc files and embedded SYLT tags.

Hierarchy (11-lyrics-engine.md):
  Level 1: SYLT embedded (scanned via library_scanner → lyrics table)
  Level 2: .lrc sidecar file (fuzzy matched)
  Level 3: DB cache (lyrics.lrc_content)
  Level 4: Online lookup (interface only, Fase 2)

Exposes sorted list of (timestamp_ms, text) tuples.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass(order=True)
class LyricLine:
    timestamp_ms: int
    text: str = field(compare=False)


LRC_LINE_RE = re.compile(r"\[(\d+):(\d+)(?:\.(\d+))?\](.*?)(?=\[|$)")


class LyricsParser:
    """Parse LRC content or SYLT tags into sorted LyricLine list."""

    @staticmethod
    def from_lrc(content: str) -> list[LyricLine]:
        """Parse plain-text LRC string → sorted list of LyricLine.

        Handles multiple timestamps per line (e.g. ``[01:00.00][01:05.00]text``).
        Malformed lines are silently skipped.
        """
        lines: list[LyricLine] = []
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            # Find all timestamp + text groups in this line
            matches = LRC_LINE_RE.findall(line)
            if not matches:
                continue

            # Take the last match's text (for multiple timestamp lines)
            text = matches[-1][3].strip()
            for m in matches:
                minutes = int(m[0])
                seconds = int(m[1])
                millis = int(m[2]) if m[2] else 0
                # .m03 format → 30ms, .03 or .030 → 30ms
                if m[2] and len(m[2]) == 1:
                    millis *= 100
                elif m[2] and len(m[2]) == 2:
                    millis *= 10
                ts = minutes * 60000 + seconds * 1000 + millis
                lines.append(LyricLine(timestamp_ms=ts, text=text))

        lines.sort()
        return lines

    @staticmethod
    def from_sylt(tag_data: bytes, encoding: str = "utf-8") -> list[LyricLine]:
        """Parse synchronised lyrics (SYLT) tag data.

        Simplified parser for LRC-format content stored in SYLT.
        For actual binary SYLT parsing, the lyric text is stored as
        LRC-equivalent text during library scanning.
        """
        try:
            text = tag_data.decode(encoding, errors="replace")
        except (UnicodeDecodeError, AttributeError):
            return []
        return LyricsParser.from_lrc(text)

    @classmethod
    def resolve(
        cls,
        file_path: str,
        lrc_content: Optional[str] = None,
        artist: str = "",
        title: str = "",
    ) -> list[LyricLine] | None:
        """Convenience: try DB content → .lrc sidecar → online → None.

        Args:
            file_path: Path to the audio file (used to find .lrc sidecar).
            lrc_content: Optional LRC string from DB cache.
            artist: Track artist for online lookup (Level 4).
            title: Track title for online lookup (Level 4).
        """
        # Level 3: DB cache
        if lrc_content:
            parsed = cls.from_lrc(lrc_content)
            if parsed:
                return parsed

        # Level 2: sidecar .lrc file
        audio = Path(file_path)
        candidates = [
            audio.with_suffix(".lrc"),
            audio.with_suffix(".LRC"),
        ]
        # Fuzzy: same stem, any dir
        for f in candidates:
            if f.exists():
                content = f.read_text(encoding="utf-8", errors="replace")
                parsed = cls.from_lrc(content)
                if parsed:
                    return parsed

        # Level 4: Online lookup (FR-5.2)
        from nocturne.config.config import cfg
        if cfg.lyricsOnline.value and title:
            from nocturne.integrations.lyrics.lyrics_online import fetch_lyrics_online
            lrc_raw = fetch_lyrics_online(artist, title)
            if lrc_raw:
                parsed = cls.from_lrc(lrc_raw)
                if parsed:
                    return parsed

        return None


def lines_to_lrc(lines: list[LyricLine]) -> str:
    """Convert LyricLine list back to LRC-format string."""
    parts = []
    for ll in lines:
        m, s = divmod(ll.timestamp_ms // 1000, 60)
        ms = ll.timestamp_ms % 1000
        parts.append(f"[{m:02d}:{s:02d}.{ms:03d}]{ll.text}")
    return "\n".join(parts)
