# coding:utf-8
"""
main_window_controller.py — Orchestrator for the entire application.

Owns the engine layer (PlayerEngine, Equalizer, AudioWorker),
all sub-controllers, and the shared state across views.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QTimer, Signal

from nocturne.data.db import get_connection
from nocturne.data.library_scanner import LibraryScanner
from nocturne.data.models import Track
from nocturne.config.config import PlayerBackend, cfg
from nocturne.core.player_engine import PlayerEngine as VLCPlayerEngine
from nocturne.core.qt_player_engine import QtPlayerEngine
from nocturne.core.equalizer import Equalizer
from nocturne.core.audio_worker import AudioWorker
from nocturne.core.lyrics_sync import LyricsParser, lines_to_lrc
from nocturne.common.signal_bus import signalBus
from nocturne.ui.controllers.base import Controller
from nocturne.ui.controllers.home_controller import HomeController
from nocturne.ui.controllers.songs_controller import SongsController
from nocturne.ui.controllers.artists_controller import ArtistsController
from nocturne.ui.controllers.albums_controller import AlbumsController
from nocturne.ui.controllers.playlist_controller import PlaylistController
from nocturne.ui.controllers.equalizer_controller import EqualizerController
from nocturne.ui.controllers.settings_controller import SettingsController


class MainWindowController(Controller):
    """Top-level orchestrator connecting engines, controllers, and UI."""

    # Signals emitted for UI to consume
    track_changed = Signal(object)  # Track
    play_state_changed = Signal(bool)
    lyrics_loaded = Signal(object, int)  # list[LyricLine], offset_ms
    scan_complete = Signal()
    volume_restored = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # ── Engine layer ──────────────────────────────────────────────
        self._vlc_backend = cfg.get(cfg.playerBackend) == PlayerBackend.VLC
        if self._vlc_backend:
            self.player_engine = VLCPlayerEngine()
            self.equalizer = Equalizer(self.player_engine._instance)
            self.equalizer.apply_preset("Flat")
            self.equalizer.attach_to_player(self.player_engine._player)
            self.player_engine.set_on_end(self._sync_current_track)
        else:
            self.player_engine = QtPlayerEngine()
            self.equalizer = Equalizer()  # no-op mode
            self.player_engine.set_on_end(self.next_track)

        self.audio_worker = AudioWorker(
            pcm_source=self.player_engine.pcm_data, parent=self
        )

        self._current_track: Optional[Track] = None
        self._music_folders: list[Path] = []
        self._playback_queue: list[Track] = []
        self._shuffled = False
        self._shuffle_order: list[int] = []

        # ── Sub-controllers ───────────────────────────────────────────
        self.home = HomeController(self)
        self.songs = SongsController(self)
        self.artists = ArtistsController(self)
        self.albums = AlbumsController(self)
        self.playlists = PlaylistController(self)
        self.equalizer_ctrl = EqualizerController(
            self.equalizer, assign_callback=self._assign_eq_to_track, parent=self
        )
        self.settings = SettingsController(self)

        # ── Signal bus wiring ─────────────────────────────────────────
        signalBus.folder_added.connect(self._on_folder_added)
        signalBus.scan_started.connect(self.scan_library)

    # ── Playback ──────────────────────────────────────────────────────

    @property
    def current_track(self) -> Optional[Track]:
        return self._current_track

    def _play(self, tracks: list[Track], start_index: int = 0) -> None:
        """Load track into engine — queue stored for next/prev."""
        self._playback_queue = list(tracks)
        self._rebuild_shuffle()
        if not tracks or start_index < 0 or start_index >= len(tracks):
            return
        track = tracks[start_index]
        if not track.path or not Path(track.path).exists():
            return
        self._save_lyrics_offset_for_current()
        self._current_track = track
        self.player_engine.load_single(track.path)
        self._on_track_changed(track)

    def _rebuild_shuffle(self) -> None:
        import random
        n = len(self._playback_queue)
        self._shuffle_order = list(range(n))
        random.shuffle(self._shuffle_order)

    def _queue_index(self) -> int:
        if not self._playback_queue or not self._current_track:
            return -1
        return next(
            (i for i, t in enumerate(self._playback_queue) if t.id == self._current_track.id),
            -1,
        )

    def toggle_shuffle(self) -> bool:
        self._shuffled = not self._shuffled
        if self._shuffled:
            self._rebuild_shuffle()
            # Re-order current position to front of shuffle list
            cur = self._queue_index()
            if cur >= 0 and cur in self._shuffle_order:
                self._shuffle_order.remove(cur)
                self._shuffle_order.insert(0, cur)
        return self._shuffled

    @property
    def is_shuffled(self) -> bool:
        return self._shuffled

    def play_track(self, track: Track) -> None:
        if track.source_type == "local":
            if not track.path or not Path(track.path).exists():
                return
        # Load all library tracks as queue context
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM tracks WHERE path IS NOT NULL ORDER BY title"
        ).fetchall()
        all_tracks = [Track.from_row(r) for r in rows]
        idx = next((i for i, t in enumerate(all_tracks) if t.id == track.id), 0)
        self._play(all_tracks, idx)

    def play_artist_tracks(self, artist: str) -> None:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM tracks WHERE artist = ? AND path IS NOT NULL ORDER BY album_id, title",
            (artist,),
        ).fetchall()
        tracks = [Track.from_row(r) for r in rows]
        self._play(tracks)

    def play_album_tracks(self, album_id: int) -> None:
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM tracks WHERE album_id = ? AND path IS NOT NULL ORDER BY title",
            (album_id,),
        ).fetchall()
        tracks = [Track.from_row(r) for r in rows]
        self._play(tracks)

    def toggle_play(self) -> None:
        self.player_engine.toggle_play()

    def _navigate(self, delta: int) -> None:
        q = self._playback_queue
        if not q or not self._current_track:
            return
        cur = self._queue_index()
        if cur < 0:
            return
        if self._shuffled:
            idx = self._shuffle_order.index(cur) if cur in self._shuffle_order else -1
            if idx < 0:
                return
            nidx = idx + delta
            if nidx < 0 or nidx >= len(self._shuffle_order):
                return
            self._play(q, self._shuffle_order[nidx])
        else:
            nidx = cur + delta
            if nidx < 0 or nidx >= len(q):
                return
            self._play(q, nidx)

    def next_track(self) -> None:
        self._navigate(1)

    def prev_track(self) -> None:
        self._navigate(-1)

    def _sync_current_track(self) -> None:
        """Called on end-of-track: advance to next."""
        self._navigate(1)

    def seek(self, ms: int) -> None:
        self.player_engine.seek(ms)

    @property
    def is_playing(self) -> bool:
        return self.player_engine.is_playing

    @property
    def position_ms(self) -> int:
        return self.player_engine.position_ms

    @property
    def duration_ms(self) -> int:
        return self.player_engine.duration_ms

    @property
    def volume(self) -> int:
        return self.player_engine.volume

    @volume.setter
    def volume(self, val: int) -> None:
        self.player_engine.volume = val

    # ── Resume ────────────────────────────────────────────────────────

    def resume_playback(self) -> None:
        state = self.player_engine.load_state()
        if not state:
            return

        vol = state.get("volume")
        if vol is not None:
            self.volume_restored.emit(vol)

        if not state.get("path"):
            return
        path = state["path"]
        if not Path(path).exists():
            return
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM tracks WHERE path = ?", (path,)
        ).fetchone()
        if not row:
            # file not in library — load standalone, no queue
            import ntpath
            title = ntpath.splitext(ntpath.basename(path))[0]
            track = Track(path=path, title=title)
            self._current_track = track
            self.player_engine.load_single(track.path)
            pos = state.get("position_ms", 0)
            if pos > 0:
                QTimer.singleShot(500, lambda: self.player_engine.seek(pos))
            self._on_track_changed(track)
            return

        track = Track.from_row(row)
        # Build full library queue and play at resumed position
        conn2 = get_connection()
        rows = conn2.execute(
            "SELECT * FROM tracks WHERE path IS NOT NULL ORDER BY title"
        ).fetchall()
        all_tracks = [Track.from_row(r) for r in rows]
        idx = next((i for i, t in enumerate(all_tracks) if t.id == track.id), 0)
        self._play(all_tracks, idx)
        pos = state.get("position_ms", 0)
        if pos > 0:
            QTimer.singleShot(500, lambda: self.player_engine.seek(pos))

    # ── Live state ────────────────────────────────────────────────────

    def save_state(self) -> None:
        self.player_engine.save_state()

    # ── Internal track lifecycle ──────────────────────────────────────

    def _on_track_changed(self, track: Track) -> None:
        self.track_changed.emit(track)
        self.play_state_changed.emit(True)

        if not self.audio_worker.isRunning():
            self.audio_worker.start()

        # Record play history
        if track.id:
            conn = get_connection()
            conn.execute(
                "INSERT INTO play_history (track_id, duration_played_ms) VALUES (?, ?)",
                (track.id, 0),
            )
            conn.commit()

        # Lyrics
        self._load_lyrics(track)

        # EQ preset
        self._apply_track_eq(track)

        self.save_state()

    # ── EQ ────────────────────────────────────────────────────────────

    def _apply_track_eq(self, track: Track) -> None:
        if not self.equalizer:
            return
        conn = get_connection()
        row = conn.execute(
            "SELECT eq_preset FROM tracks WHERE id = ?", (track.id,)
        ).fetchone()
        eq_name = row["eq_preset"] if row and row["eq_preset"] else "Flat"
        self.equalizer.apply_preset(eq_name)

    def _assign_eq_to_track(self, preset_name: str) -> None:
        if not self._current_track or not self._current_track.id:
            return
        conn = get_connection()
        conn.execute(
            "UPDATE tracks SET eq_preset = ? WHERE id = ?",
            (preset_name, self._current_track.id),
        )
        conn.commit()

    # ── Lyrics ────────────────────────────────────────────────────────

    def _load_lyrics(self, track: Track) -> None:
        conn = get_connection()
        row = conn.execute(
            "SELECT lrc_content, offset_ms FROM lyrics WHERE track_id = ?",
            (track.id,),
        ).fetchone()
        if row:
            lrc_content = row["lrc_content"]
            offset = row["offset_ms"] or 0
        else:
            lrc_content = None
            offset = 0

        lines = LyricsParser.resolve(
            track.path or "",
            lrc_content,
            artist=track.artist or "",
            title=track.title,
        )
        self.lyrics_loaded.emit(lines or [], offset)

        if lines and not lrc_content and track.id:
            lrc_text = lines_to_lrc(lines)
            if lrc_text:
                conn.execute(
                    "INSERT OR REPLACE INTO lyrics (track_id, lrc_content) VALUES (?, ?)",
                    (track.id, lrc_text),
                )
                conn.commit()

    def save_lyrics_offset(self, track: Track, offset_ms: int) -> None:
        if not track or not track.id or offset_ms == 0:
            return
        conn = get_connection()
        conn.execute(
            "INSERT OR REPLACE INTO lyrics (track_id, lrc_content, offset_ms) "
            "VALUES (?, COALESCE((SELECT lrc_content FROM lyrics WHERE track_id = ?), ''), ?)",
            (track.id, track.id, offset_ms),
        )
        conn.commit()

    def _save_lyrics_offset_for_current(self) -> None:
        if self._current_track:
            conn = get_connection()
            row = conn.execute(
                "SELECT offset_ms FROM lyrics WHERE track_id = ?",
                (self._current_track.id,),
            ).fetchone()
            offset = row["offset_ms"] if row else 0
            self.save_lyrics_offset(self._current_track, offset)

    # ── Library scanning ──────────────────────────────────────────────

    @property
    def music_folders(self) -> list[Path]:
        return list(self._music_folders)

    def scan_library(self) -> None:
        if not self._music_folders:
            return

        conn = get_connection()
        scanner = LibraryScanner(conn)
        scanner.scan(self._music_folders)
        self.scan_complete.emit()

    def add_music_folder(self, folder: str) -> None:
        path = Path(folder)
        if path.is_dir() and path not in self._music_folders:
            self._music_folders.append(path)

    def _on_folder_added(self, folder: str) -> None:
        self.add_music_folder(folder)
