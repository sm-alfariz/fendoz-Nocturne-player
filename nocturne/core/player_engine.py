# coding:utf-8
"""
player_engine.py — libVLC wrapper for audio playback & PCM extraction.

Single audio engine — no fallback to QMediaPlayer (05-system-architecture.md).
"""

from __future__ import annotations

from nocturne.core.base_player_engine import BasePlayerEngine


class PlayerEngine(BasePlayerEngine):
    """Manages libVLC instance, media playback, and PCM extraction for FFT."""

    def __init__(self) -> None:
        super().__init__()

        import vlc as _vlc
        global vlc
        vlc = _vlc

        import platform
        vlc_args = []
        if platform.system() == "Linux":
            vlc_args = ["--no-xlib", "--aout=auto", "--quiet"]
        self._instance = vlc.Instance(*vlc_args)
        self._player = self._instance.media_player_new()
        self._list_player = self._instance.media_list_player_new()
        self._list = self._instance.media_list_new()

        self._list_player.set_media_player(self._player)
        self._list_player.set_media_list(self._list)

        # End-of-track → auto-advance
        self._player.event_manager().event_attach(
            vlc.EventType.MediaPlayerEndReached, self._on_end_reached
        )
        self._player.event_manager().event_attach(
            vlc.EventType.MediaPlayerMediaChanged, self._on_media_changed
        )

        # Callbacks
        self._on_track_change = None
        self._on_media_change = None

    # ── Playback control ──────────────────────────────────────────────

    def play(self) -> None:
        self._pcm.start()
        self._list_player.play()

    def pause(self) -> None:
        self._pcm.stop()
        self._list_player.pause()

    def stop(self) -> None:
        self._pcm.stop()
        self._list_player.stop()

    def toggle_play(self) -> None:
        if self._player.is_playing():
            self.pause()
        else:
            self.play()

    def next(self) -> None:
        self._list_player.next()

    def previous(self) -> None:
        self._list_player.previous()

    @property
    def list_index(self) -> int:
        try:
            return self._list_player.get_playlist_index()
        except Exception:
            return -1

    def seek(self, ms: int) -> None:
        self._player.set_time(ms)

    @property
    def is_playing(self) -> bool:
        return self._player.is_playing()

    @property
    def position_ms(self) -> int:
        return self._player.get_time()

    @property
    def duration_ms(self) -> int:
        return self._player.get_length()

    @property
    def volume(self) -> int:
        return self._player.audio_get_volume()

    @volume.setter
    def volume(self, val: int) -> None:
        self._player.audio_set_volume(max(0, min(100, val)))

    # ── Repeat (VLC-specific backend) ─────────────────────────────────

    def _apply_repeat(self) -> None:
        if self._repeat_mode == "one":
            self._list_player.set_playback_mode(vlc.PlaybackMode.loop)
        elif self._repeat_mode == "all":
            self._list_player.set_playback_mode(vlc.PlaybackMode.loop)
        else:
            self._list_player.set_playback_mode(vlc.PlaybackMode.default)

    def toggle_shuffle(self) -> bool:
        self._shuffle = not self._shuffle
        if self._shuffle:
            import random
            self._shuffled_indices = list(range(len(self._playlist_paths)))
            random.shuffle(self._shuffled_indices)
        return self._shuffle

    # ── Playlist management ───────────────────────────────────────────

    def load_playlist(self, paths: list[str], start_index: int = 0) -> None:
        """Load a list of file paths into the media list and start playback."""
        self._list = self._instance.media_list_new()
        for p in paths:
            self._list.add_media(self._instance.media_new(p))
        self._playlist_paths = paths
        self._list_player.set_media_list(self._list)
        self._pcm.start()
        self._list_player.play_item_at_index(start_index)

    def load_single(self, path: str) -> None:
        """Load a single file (for resume — no list/queue)."""
        from urllib.parse import quote
        mrl = "file://" + quote(str(path))
        media = self._instance.media_new(mrl)
        self._player.set_media(media)

    def set_on_media_change(self, callback) -> None:
        """Register callback when VLC advances to next media in list."""
        self._on_media_change = callback

    def _on_end_reached(self, event) -> None:
        """VLC end-of-track event — let list player advance, then sync UI."""
        if self._on_end:
            self._on_end()

    def _on_media_changed(self, event) -> None:
        """VLC media changed event — current media switched (next/prev in list)."""
        if self._on_media_change:
            self._on_media_change()

    # ── Track info ────────────────────────────────────────────────────

    @property
    def current_media_path(self) -> str | None:
        from urllib.parse import unquote
        media = self._player.get_media()
        if media:
            mrl = media.get_mrl()
            if mrl and mrl.startswith("file://"):
                return unquote(mrl[len("file://"):])
            return mrl
        return None

    def cleanup(self) -> None:
        """Release VLC resources."""
        self._pcm.stop()
        self._player.stop()
        self._instance.release()
