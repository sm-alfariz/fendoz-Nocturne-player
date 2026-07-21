# coding:utf-8
"""
main_window_controller.py — Orchestrator for the entire application.

Owns the engine layer (PlayerEngine, Equalizer, AudioWorker),
all sub-controllers, and the shared state across views.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, QTimer, Signal

from nocturne.data.db import get_connection
from nocturne.data.library_scanner import ScanWorker
from nocturne.data.models import Track
from nocturne.config.config import PlayerBackend, cfg
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
from nocturne.ui.controllers.settings_controller import SettingsController


logger = logging.getLogger(__name__)


class MainWindowController(Controller):
    """Top-level orchestrator connecting engines, controllers, and UI."""

    # Signals emitted for UI to consume
    track_changed = Signal(object)  # Track
    play_state_changed = Signal(bool)
    lyrics_loaded = Signal(object, int)  # list[LyricLine], offset_ms
    scan_complete = Signal()
    scan_progress = Signal(int, int)  # current, total
    volume_restored = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        # ── Engine layer ──────────────────────────────────────────────
        self._vlc_backend = cfg.get(cfg.playerBackend) == PlayerBackend.VLC
        if self._vlc_backend:
            from nocturne.core.player_engine import PlayerEngine as VLCPlayerEngine
            self.player_engine = VLCPlayerEngine()
            self.equalizer = Equalizer(self.player_engine._instance)
            self.equalizer.apply_preset("Flat")
            self.equalizer.attach_to_player(self.player_engine._player)
            # Dispatch to main thread — VLC fires events on libvlc event thread.
            # 500ms delay gives VLC time to update its internal list_index after auto-advance.
            self.player_engine.set_on_end(
                lambda: QTimer.singleShot(500, self._sync_current_track)
            )
            self.player_engine.set_on_media_change(
                lambda: QTimer.singleShot(0, self._on_vlc_media_changed)
            )
        else:
            self.player_engine = QtPlayerEngine()
            self.equalizer = Equalizer()  # no-op mode
            self.player_engine.set_on_end(self.next_track)

        self.audio_worker = AudioWorker(
            pcm_source=self.player_engine.pcm_data, parent=self
        )

        # Poll timer — detects VLC auto-advance when events are unreliable
        if self._vlc_backend:
            self._poll_timer = QTimer(self)
            self._poll_timer.setInterval(1000)
            self._poll_timer.timeout.connect(self._poll_vlc_track)
            self._poll_timer.start()

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
        self.settings = SettingsController(self)

        # ── Signal bus wiring ─────────────────────────────────────────
        signalBus.folder_added.connect(self._on_folder_added)

    # ── Playback ──────────────────────────────────────────────────────

    @property
    def current_track(self) -> Optional[Track]:
        return self._current_track

    def _play(self, tracks: list[Track], start_index: int = 0) -> None:
        """Load all tracks into VLC list player for native next/prev."""
        self._playback_queue = list(tracks)
        self._rebuild_shuffle()
        if not tracks or start_index < 0 or start_index >= len(tracks):
            return
        track = tracks[start_index]
        if not track.path:
            return
        if track.source_type == "local" and not Path(track.path).exists():
            return
        self._save_lyrics_offset_for_current()
        self._current_track = track
        paths = [t.path or "" for t in tracks]
        self.player_engine.load_playlist(paths, start_index)
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

    def play_track(self, track: Track, queue: list[Track] | None = None) -> None:
        if track.source_type == "local":
            if not track.path or not Path(track.path).exists():
                return
        elif track.source_type == "soundcloud":
            self._refresh_sc_stream(track)
        if queue is not None:
            idx = next((i for i, t in enumerate(queue) if t.id == track.id), 0)
            self._play(queue, idx)
        else:
            # Fallback: all library tracks
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
        if self._vlc_backend:
            self.player_engine.next()
        else:
            self._navigate(1)

    def prev_track(self) -> None:
        if self._vlc_backend:
            self.player_engine.previous()
        else:
            self._navigate(-1)

    def _sync_current_track(self) -> None:
        """Called on end-of-track: sync UI with VLC's auto-advanced track."""
        if self._vlc_backend:
            self._on_vlc_media_changed()
            return
        self._navigate(1)

    def _poll_vlc_track(self) -> None:
        """Poll VLC to detect auto-advance when events are unreliable."""
        if not self._vlc_backend or not self._playback_queue:
            return
        path = self.player_engine.current_media_path
        if not path:
            return
        from pathlib import Path as PPath
        target = str(PPath(path).resolve())
        track = next(
            (t for t in self._playback_queue if t.path and str(PPath(t.path).resolve()) == target),
            None,
        )
        if track and track != self._current_track:
            self._save_lyrics_offset_for_current()
            self._current_track = track
            self.player_engine.save_state()
            self._on_track_changed(track)

    def _on_vlc_media_changed(self) -> None:
        """VLC list player advanced — sync current track and UI."""
        if not self._playback_queue:
            self._current_track = None
            return
        # MediaListPlayer has no get_playlist_index — match by current media path
        path = self.player_engine.current_media_path
        if not path:
            QTimer.singleShot(300, self._on_vlc_media_changed)
            return
        from pathlib import Path as PPath
        target = str(PPath(path).resolve())
        track = next(
            (t for t in self._playback_queue if t.path and str(PPath(t.path).resolve()) == target),
            None,
        )
        if track:
            self._save_lyrics_offset_for_current()
            self._current_track = track
            self.player_engine.save_state()
            self._on_track_changed(track)

    def _refresh_sc_stream(self, track: Track) -> None:
        """Re-resolve expired SoundCloud stream URL before playback."""
        if not track.source_url:
            return
        from nocturne.integrations.soundcloud.resolver import get_stream
        from nocturne.data.db import upsert_sc_track
        try:
            new_stream = get_stream(track.source_url)
            if new_stream:
                upsert_sc_track({"source_url": track.source_url, "stream_url": new_stream})
                track.path = new_stream
        except Exception:
            logger.warning("Failed to refresh SC stream for: %s", track.source_url)

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
            title = Path(path).stem
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

        from nocturne.data.db import get_db_path
        db_path = get_db_path()
        # QThread + ScanWorker for non-blocking scan
        self._scan_thread = QThread(self)
        self._scan_worker = ScanWorker(self._music_folders, db_path)
        self._scan_worker.moveToThread(self._scan_thread)
        self._scan_thread.started.connect(self._scan_worker.run)
        self._scan_worker.progress.connect(self._on_scan_progress)
        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.finished.connect(self._scan_thread.quit)
        self._scan_thread.finished.connect(self._scan_worker.deleteLater)
        self._scan_thread.finished.connect(self._scan_thread.deleteLater)
        self._scan_thread.start()

    def _on_scan_progress(self, current: int, total: int) -> None:
        self.scan_progress.emit(current, total)

    def _on_scan_finished(self, new_tracks: int, updated_tracks: int) -> None:
        logger.info("Scan complete: %d new, %d updated", new_tracks, updated_tracks)
        self.scan_complete.emit()

    def add_music_folder(self, folder: str) -> None:
        path = Path(folder)
        if path.is_dir() and path not in self._music_folders:
            self._music_folders.append(path)

    def _on_folder_added(self, folder: str) -> None:
        self.add_music_folder(folder)
