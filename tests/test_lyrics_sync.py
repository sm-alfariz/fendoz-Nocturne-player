# coding:utf-8
"""Test lyrics_sync.py — LyricsParser and lines_to_lrc."""

from __future__ import annotations

from pathlib import Path

from nocturne.core.lyrics_sync import LyricLine, LyricsParser, lines_to_lrc

SIMPLE_LRC = """[00:00.00]Intro
[00:05.50]First line
[01:30.00]Chorus start
"""

MULTI_TS_LRC = "[01:00.00][01:05.00]Repeated line"

MALFORMED_LRC = "not a timestamp line\n[bad\n\n"

ENHANCED_LRC = "[00:01.50] <00:00.70> lin<00:00.84>ew<00:01.05>ye<00:01.29>s"

ONELINE_LRC = "[03:00.00]Finale"


class TestFromLrc:
    def test_simple_lines(self) -> None:
        result = LyricsParser.from_lrc(SIMPLE_LRC)
        assert len(result) == 3
        assert result[0] == LyricLine(timestamp_ms=0, text="Intro")
        assert result[1] == LyricLine(timestamp_ms=5_500, text="First line")
        assert result[2] == LyricLine(timestamp_ms=90_000, text="Chorus start")

    def test_sorted_order(self) -> None:
        result = LyricsParser.from_lrc(ONELINE_LRC + "\n" + SIMPLE_LRC)
        # Should be sorted ascending
        timestamps = [line.timestamp_ms for line in result]
        assert timestamps == sorted(timestamps)

    def test_multi_timestamp_line(self) -> None:
        result = LyricsParser.from_lrc(MULTI_TS_LRC)
        assert len(result) == 2
        assert all(ln.text == "Repeated line" for ln in result)
        assert result[0].timestamp_ms == 60_000
        assert result[1].timestamp_ms == 65_000

    def test_malformed_returns_empty(self) -> None:
        result = LyricsParser.from_lrc(MALFORMED_LRC)
        assert result == []

    def test_empty_string(self) -> None:
        assert LyricsParser.from_lrc("") == []

    def test_enhanced_lrc_word_level(self) -> None:
        result = LyricsParser.from_lrc(ENHANCED_LRC)
        # Enhanced LRC with word-level timestamps gets parsed, text includes tags
        assert len(result) == 1
        assert result[0].timestamp_ms == 1_500

    def test_millis_formats(self) -> None:
        # .m03 format (1-digit) and .03 format (2-digit)
        lrc = "[00:00.03]Three\n[00:00.3]Three0\n"
        result = LyricsParser.from_lrc(lrc)
        assert result[0].timestamp_ms == 30
        assert result[1].timestamp_ms == 300


class TestFromSylt:
    def test_decodes_utf8_lrc_content(self) -> None:
        result = LyricsParser.from_sylt(SIMPLE_LRC.encode("utf-8"))
        assert len(result) == 3

    def test_garbage_bytes_returns_empty(self) -> None:
        result = LyricsParser.from_sylt(b"\xff\xfe\x00\x01\x02")
        assert result == []

    def test_empty_bytes(self) -> None:
        assert LyricsParser.from_sylt(b"") == []


class TestResolve:
    def test_uses_lrc_content_when_provided(self) -> None:
        result = LyricsParser.resolve("/fake/path.mp3", lrc_content=SIMPLE_LRC)
        assert result is not None
        assert len(result) == 3

    def test_sidecar_lrc_file(self, tmp_path: Path) -> None:
        lrc_file = tmp_path / "song.lrc"
        lrc_file.write_text(SIMPLE_LRC, encoding="utf-8")
        audio = str(tmp_path / "song.mp3")
        result = LyricsParser.resolve(audio)
        assert result is not None
        assert len(result) == 3

    def test_sidecar_not_found_returns_none(self) -> None:
        result = LyricsParser.resolve("/nonexistent/song.mp3")
        assert result is None


class TestLinesToLrc:
    def test_roundtrip(self) -> None:
        lines = [
            LyricLine(timestamp_ms=0, text="Start"),
            LyricLine(timestamp_ms=10_000, text="Ten seconds"),
        ]
        lrc = lines_to_lrc(lines)
        reparsed = LyricsParser.from_lrc(lrc)
        assert reparsed == lines

    def test_empty_list(self) -> None:
        assert lines_to_lrc([]) == ""
