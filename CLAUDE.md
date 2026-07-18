# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run app
.venv/bin/python -m nocturne

# Run tests
.venv/bin/python -m pytest tests/ -v

# Run a single test
.venv/bin/python -m pytest tests/test_signal_bus.py -v

# Lint (ruff)
.venv/bin/python -m ruff check nocturne/
.venv/bin/python -m ruff check nocturne/ --fix

# Type check (optional — no mypy config yet)
.venv/bin/python -m ruff check --select ANN nocturne/
```

## Architecture

### Stack
- **UI**: PySide6 (QtWidgets, no QML) + PyQt-Fluent-Widgets
- **Audio engine**: libVLC (python-vlc) — sole backend, no QMediaPlayer fallback
- **FFT/visualizer**: numpy FFT in QThread (AudioWorker), rendered via QPainter
- **Database**: SQLite (sqlite3 stdlib) with WAL mode + PRAGMA user_version migrations
- **Metadata**: mutagen (ID3, Vorbis, SYLT lyrics, embedded artwork)

### Module layout
```
nocturne/
├── __main__.py         # Entry point: QApplication setup, theme force, crash handler
├── core/               # Audio engine + signal processing (no Qt imports)
│   ├── player_engine.py   # libVLC wrapper: playback, playlist, volume, shuffle
│   ├── audio_worker.py    # QThread for async FFT (emits spectrum_ready Signal → UI)
│   ├── pcm_capture.py     # PCM ring buffer from VLC audio callbacks (stub: returns None)
│   ├── equalizer.py       # 10-band EQ via VLC native AudioEqualizer API
│   └── lyrics_sync.py     # .lrc / SYLT parser → sorted LyricLine list
├── data/               # Persistence layer (pure SQLite, no ORM)
│   ├── db.py              # init_db, get_connection, migrations via user_version
│   ├── models.py          # Track/Album/Playlist/EQPreset dataclasses (from_row)
│   ├── library_scanner.py # Incremental scan: mutagen extraction, mtime dedup
│   ├── playlist_manager.py# CRUD, reorder, .m3u import/export
│   └── relocate.py        # Batch path UPDATE when folder root moves
├── ui/
│   ├── main_window.py     # 3-column layout: TopBar | Sidebar+Stage | Lyrics
│   ├── components/
│   │   ├── player_bar.py      # Bottom dock: transport, volume, progress, repeat/shuffle
│   │   ├── ring_visualizer.py # QPainter ring around album art + SpectrumBar
│   │   ├── lyrics_panel.py    # Right-side scroll panel, auto-scroll, SYNCED badge
│   │   └── soundcloud_dialog.py# URL input dialog for online source
│   └── views/             # One file per sidebar nav item
│       ├── songs_view.py      # QSortFilterProxyModel + TableView, double-click → play
│       ├── albums_view.py     # FlowLayout cards, click → play album
│       ├── artists_view.py    # FlowLayout cards, click → play artist
│       ├── playlist_view.py   # Splitter: playlist list + detail with track list
│       ├── equalizer_view.py  # 10 sliders + preset dropdown
│       └── setting_interface.py # Library folders, online toggles, reduce motion, theme
├── config/
│   └── config.py         # QConfig singleton (cfg) — theme, DPI, language, online toggles
├── common/
│   └── signal_bus.py     # Singleton SignalBus: folder_added, scan_started, play_toggled
└── integrations/
    └── soundcloud/        # Isolated module for online streaming (Fase 2, not wired yet)
```

### Data flow (playback)
```
Double-click song → SongsView.track_activated → MainWindow._play_track
  → PlayerEngine.load_single(path) → libVLC plays audio
  → MainWindow._on_track_changed → UI updates + AudioWorker.start() + lyrics timer
```

### Key patterns
- **Views load data on demand**: call `view.load()` after scan — no auto-refresh
- **Cross-component communication**: via `signalBus` singleton (SignalBus) — never direct widget coupling
- **Theme tokens**: `ui/theme/tokens.py` — Color, Fonts, Spacing dataclasses, imported as `Color.ACCENT`
- **DB connection**: `get_connection()` returns `sqlite3.Row`-based conn. Worker threads need `check_same_thread=False`
- **Track model**: `Track.from_row(sqlite3.Row)` filters unknown columns — safe for `SELECT *` joins
- **QThread safety**: AudioWorker never touches main thread UI; emits `Signal(object)` → slot updates widget

### PRD (archive/MP3Player-PRD/)
Full requirements spec in 14 markdown files. Key IDs: FR-1.x (playback), FR-2.x (playlists), FR-3.x (EQ), FR-4.x (visualizer), FR-5.x (lyrics).

### Known gaps
- FR-4.1: PCM capture for visualizer is a stub — `pcm_capture.py` returns None (needs PulseAudio monitor source)
- FR-6.x: SoundCloud integration not wired (Fase 2)
- FR-5.2: Online lyrics lookup not implemented (Fase 2)
