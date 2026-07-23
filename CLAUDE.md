# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.


# Role: Senior PySide6 UI/UX Engineer

You are a Senior Python Developer specializing in PySide6 desktop applications. You write clean, maintainable, and highly responsive GUI code following modern Qt best practices.

## PySide6 Conventions

- **Threading:** NEVER perform heavy computations or I/O on the main GUI thread. Offload long-running tasks using `QThread` and `QObject` worker instances, communicating via signals and slots.
- **Layouts:** Use layout managers (`QVBoxLayout`, `QHBoxLayout`, `QGridLayout`) dynamically instead of absolute positioning.
- **MVC Architecture:** Enforce separation of concerns. Keep business logic separate from view rendering.
- **Styling:** Use Qt Style Sheets (QSS) for distinct theming, but prefer proper widget styling and layout structure as the foundation.
- **Signals & Slots:** Use the modern PySide6 decorator syntax (`@Slot(...)`) for signal connections to ensure type safety and proper signature handling.

## Code Standards
- Always use Python type hinting.
- Follow PEP 8 guidelines.
- Write docstrings for all classes and public methods.
- Avoid using `from PySide6.QtWidgets import *`. Import explicitly (e.g., `from PySide6.QtWidgets import QApplication, QMainWindow`).

## Do NOT
- Do not let the UI freeze during operations (e.g., file saving, network requests).
- Do not use `time.sleep()` inside UI methods.
- Do not mix PyQt5 or PyQt6 legacy code with PySide6.
- Do not hardcode colors or sizes; use palettes or derive them via QSS.

## Workflow Integration
Whenever creating a new UI module, include both the UI view logic and a brief explanation of how to hook up your signals and slots.



## Commands

```bash
# Run app
.venv/bin/python -m nocturne

# Run all tests (76 tests, 10 files)
.venv/bin/python -m pytest tests/ -v

# Run a single test file
.venv/bin/python -m pytest tests/test_lyrics_sync.py -v

# Lint (ruff)
.venv/bin/python -m ruff check nocturne/
.venv/bin/python -m ruff check tests/
.venv/bin/python -m ruff check nocturne/ --fix

# Type check (optional — no mypy config yet)
.venv/bin/python -m ruff check --select ANN nocturne/
```

## Architecture

### Stack
- **UI**: PySide6 (QtWidgets, no QML) + PyQt-Fluent-Widgets
- **Audio engine**: libVLC (python-vlc, lazy import) — default, with QMediaPlayer fallback (config toggle in Settings)
- **FFT/visualizer**: numpy FFT in QThread (AudioWorker), rendered via QPainter — real PCM via `parec` (Linux) or WASAPI loopback `pyaudiowpatch` (Windows)
- **Database**: SQLite (sqlite3 stdlib) with WAL mode + PRAGMA user_version migrations
- **Metadata**: mutagen (ID3, Vorbis, SYLT lyrics, embedded artwork)

### Module layout
```
nocturne/
├── __main__.py         # Entry point: QApplication setup, theme force, crash handler
├── core/               # Audio engine + signal processing (no Qt imports)
│   ├── player_engine.py   # libVLC wrapper: playback, queue navigation, end-of-track callback
│   ├── qt_player_engine.py# QMediaPlayer backend (alternative to VLC)
│   ├── audio_worker.py    # QThread for async FFT (emits spectrum_ready Signal → UI)
│   ├── pcm_capture.py     # PCM ring buffer from PulseAudio monitor (parec subprocess) + synthetic IFFT fallback
│   ├── equalizer.py       # 10-band EQ via VLC native AudioEqualizer API
│   └── lyrics_sync.py     # .lrc / SYLT parser → sorted LyricLine list
├── data/               # Persistence layer (pure SQLite, no ORM)
│   ├── db.py              # init_db, get_connection, migrations via user_version
│   ├── models.py          # Track/Album/Playlist/EQPreset dataclasses (from_row)
│   ├── library_scanner.py # Incremental scan: mutagen extraction, mtime dedup
│   ├── scan_worker.py     # ScanWorker QObject for background scan signals
│   ├── playlist_manager.py# CRUD, reorder, .m3u import/export
│   └── relocate.py        # Batch path UPDATE when folder root moves
├── ui/
│   ├── main_window.py     # 3-column layout: Sidebar+Stage | Lyrics
│   ├── components/
│   │   ├── player_bar.py      # Bottom dock: custom widget with gradient progress, transport, time labels
│   │   ├── miniplayer.py      # Frameless always-on-top miniplayer with artwork + transport
│   │   ├── ring_visualizer.py # QPainter ring around album art + SpectrumBar
│   │   ├── top_bar.py         # Top bar: logo, search, miniplayer/settings/SC buttons
│   │   ├── stage_widget.py    # Center column: ring visualizer + track info + spectrum
│   │   ├── lyrics_panel.py    # Right-side karaoke typing effect via QTextEdit HTML, Enhanced LRC word-level highlight
│   │   ├── scan_progress_overlay.py  # Semi-transparent overlay with ProgressBar during scan
│   │   └── soundcloud_dialog.py# URL input dialog for online source
│   ├── workers/
│   │   └── __init__.py     # SearchWorker, StreamWorker, ResolveWorker (SoundCloud)
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
│   └── signal_bus.py     # Singleton SignalBus: folder_added, scan_started, play_toggled, playlist_changed
└── integrations/
    └── soundcloud/        # Isolated module for online streaming (Fase 2, not wired yet)
```

### Data flow (playback)
```
Double-click song → SongsView.track_activated → MainWindow._play_track
  → MainWindowController._play() → loads queue (all tracks) + calls load_single
  → PlayerEngine.load_single(path) → libVLC plays audio
  → MainWindow._on_track_changed → UI updates + AudioWorker.start() + lyrics timer
  → End-of-track → _sync_current_track() / next_track() → _navigate(1) → _play()
```

### Queue system
```
_playback_queue: list[Track] — set by each view context (all tracks / artist / album)
_shuffle_order: list[int] — random permutation, rebuilt on shuffle toggle
next_track/prev_track → _navigate(delta) → uses shuffle order if active
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
- FR-4.1: PCM capture — Linux (PulseAudio) and Windows (WASAPI) done, ALSA and macOS not implemented
- FR-6.x: SoundCloud integration not wired (Fase 2)
- FR-5.2: Online lyrics lookup not implemented (Fase 2)
- FR-3.4: EQ preset per-track apply not implemented
- Integration tests: player_engine, library_scanner, audio_worker need real audio I/O (skipped)
- UI tests: views, components, controllers not yet covered
- Tray: Wayland support depends on compositor — may need `qt6-wayland` or fallback to no-tray mode

## graphify

This project has a knowledge graph at `graphify-out/` with god nodes, community structure, and cross-file relationships. **Use the graph before reading source files** — it's faster and uses fewer tokens.

### MCP Server (preferred for agents)

A graphify MCP server is configured in `.mcp.json`. Available tools:
- `graphify_query` — BFS traversal for codebase questions
- `graphify_explain` — plain-language explanation of a concept
- `graphify_path` — shortest path between two concepts
- `graphify_affected` — what would break if I change X

**Use these MCP tools instead of Bash `graphify` CLI when available.**

### Query commands (Bash fallback)

```bash
graphify query "how does playback work"     # BFS traversal
graphify path "PlayerEngine" "LyricsPanel"  # shortest path
graphify explain "MainWindowController"     # node explanation
graphify affected "Track"                   # impact analysis
graphify update .                           # rebuild after code changes
```

### When to use graph vs source

| Use graph for | Use source for |
|---|---|
| "How does X work?" | Reading a specific function's implementation |
| "What calls X?" | Understanding line-by-line logic |
| "What would break?" | Verifying exact code before editing |
| Architecture overview | After `graphify update .` confirms no drift |

### Agent rules
- For codebase questions, **first use graphify MCP tools or `graphify query`**
- Use `graphify path` for relationships, `graphify explain` for focused concepts
- Read `GRAPH_REPORT.md` only for broad architecture review
- After modifying code, run `graphify update .` to keep the graph current
- Save useful Q&A with `graphify save-result --question "..." --answer "..." --outcome useful`
