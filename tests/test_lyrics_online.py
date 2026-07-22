# coding:utf-8
"""Test lyrics_online.py — fetch_lyrics_online with mocked HTTP."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from nocturne.integrations.lyrics.lyrics_online import fetch_lyrics_online


class TestFetchLyricsOnline:
    def test_empty_title_returns_none(self) -> None:
        assert fetch_lyrics_online("Artist", "") is None

    def test_404_returns_none(self) -> None:
        import httpx
        with patch("httpx.get") as mock_get:
            mock_get.return_value.raise_for_status.side_effect = (
                httpx.HTTPStatusError("Not Found", request=MagicMock(), response=MagicMock())
            )
            mock_get.return_value.status_code = 404
            result = fetch_lyrics_online("Artist", "Unknown Track")
            assert result is None

    def test_success_returns_synced_lyrics(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"syncedLyrics": "[00:00.00]Test lyric"}
        mock_resp.raise_for_status.return_value = None
        with patch("httpx.get", return_value=mock_resp):
            result = fetch_lyrics_online("Artist", "Track")
            assert result == "[00:00.00]Test lyric"

    def test_falls_back_to_plain_lyrics(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"plainLyrics": "Plain text line"}
        mock_resp.raise_for_status.return_value = None
        with patch("httpx.get", return_value=mock_resp):
            result = fetch_lyrics_online("Artist", "Track")
            assert result == "Plain text line"
