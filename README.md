# Nocturne Music Player Offline First MP3 Player 🎵

<div style="text-align: center;">
  <img src="resource/img/icon.png" alt="APP MAIN LOGO">
</div>

[![CI](https://github.com/sm-alfariz/fendoz-Nocturne-player/actions/workflows/ci.yml/badge.svg)](https://github.com/sm-alfariz/fendoz-Nocturne-player/actions/workflows/ci.yml)

## 📷️ Screen Shoot
| Screen Shoot | Desc |
| --- | --- |
| ![mockup](./screen-shoots/mockup-nocturne.png) | Main App (Main Player) |
| ![mockup](./screen-shoots/miniplayer.png) | Mini Player |
| ![mockup](./screen-shoots/expand-miniplayer.png) | Expand Mini Player |



Nocturne adalah aplikasi pemutar musik desktop premium dengan pendekatan **offline-first**. Semua fungsi inti berjalan penuh tanpa koneksi internet. Dirancang untuk audiophile dan kolektor musik lokal.

## Fitur

### Inti
- **Pemutaran audio** — VLC (libvlc) sebagai engine utama, fallback QMediaPlayer
- **Queue cerdas** — konteks queue berdasarkan view (semua lagu, per-artis, per-album)
- **Shuffle** — acak queue dengan Python, bukan VLC internal
- **Next/Prev** — navigasi dalam queue, auto-advance saat lagu selesai
- **Repeat** — mode off / one / all
- **Resume** — melanjutkan posisi terakhir saat startup

### Visualizer
- **Ring visualizer** — segmen melingkar di sekitar album art, reaktif ke FFT
- **Spectrum bar** — 50 bar horizontal dengan peak-hold + smooth decay
- **PCM capture** — real audio: PulseAudio (`parec`) di Linux, WASAPI loopback (`pyaudiowpatch`) di Windows, fallback sintetik
- **FFT** — numpy rfft di QThread (AudioWorker), 30 fps

### Lirik
- **Karaoke typing effect** — per-word highlight dengan HTML QTextEdit
- **Enhanced LRC** — dukungan format `<mm:ss.xx>kata` untuk highlight per karakter
- **LRC sidecar** — deteksi otomatis file `.lrc` di folder sama
- **SYLT embedded** — ekstraksi dari tag ID3
- **Offset adjustment** — tombol ±100ms untuk sinkronisasi manual

### Library
- **Metadata extraction** — mutagen untuk ID3, Vorbis, FLAC, APIC
- **Incremental scan** — skip file dengan mtime sama
- **SQLite** — WAL mode, user_version migrations
- **Album art** — embedded tag → fallback gradient
- **Playlist** — CRUD, reorder, .m3u import/export
- **Relocate** — batch update path saat folder root pindah

### Equalizer
- **10-band** — via VLC native AudioEqualizer API
- **Preset** — simpan/muat preset per lagu

### UI
- **Dark navy theme** — 3-column layout (sidebar | stage | lyrics)
- **PySide6 + QFluentWidgets** — komponen modern
- **Reduce motion** — aksesibilitas
- **System tray** — minimize to tray, notifikasi tetap jalan
- **Miniplayer** — window kecil always-on-top dengan kontrol pemutaran
- **Custom player bar** — progress bar gradient, tombol transport, time labels

## Instalasi

```bash
# Clone
git clone https://github.com/fendoz/nocturne-player.git
cd nocturne-player

# Buat virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Jalankan
python -m nocturne
```

### Dependencies sistem (Linux)

```bash
# VLC
sudo pacman -S vlc   # Arch
sudo apt install vlc # Debian/Ubuntu

# PulseAudio (untuk PCM capture)
sudo pacman -S pulseaudio   # Arch
sudo apt install pulseaudio # Debian/Ubuntu
```

### Dependencies sistem (Windows)

```powershell
# VLC — download dari https://www.videolan.org/vlc/ lalu tambah ke PATH
# PCM capture (opsional, untuk visualizer real audio):
pip install pyaudiowpatch
```

## Development

```bash
# Lint
.venv/bin/python -m ruff check nocturne/

# Auto-fix
.venv/bin/python -m ruff check nocturne/ --fix

# Run all tests (76 tests across 10 test files)
.venv/bin/python -m pytest tests/ -v

# Run a specific test file
.venv/bin/python -m pytest tests/test_lyrics_sync.py -v
```

## Tech Stack

| Lapisan | Teknologi |
|---------|-----------|
| UI | PySide6, QFluentWidgets |
| Audio engine | libVLC (python-vlc), QMediaPlayer |
| FFT/visualizer | numpy, QPainter, QThread |
| Database | SQLite (stdlib) WAL mode |
| Metadata | mutagen |
| PCM capture | PulseAudio `parec` (Linux), WASAPI loopback `pyaudiowpatch` (Windows), numpy |

## Todo / Known Gaps

- [ ] FR-4.1: PCM capture — Linux (PulseAudio) dan Windows (WASAPI) done, ALSA dan macOS belum
- [ ] FR-5.2: Online lyrics lookup (belum)
- [ ] FR-6.x: SoundCloud integration (Fase 2, belum fully wired)
- [ ] FR-3.4: EQ preset per-track apply
- [ ] Integration tests: player_engine, library_scanner, audio_worker need real audio I/O
- [ ] UI tests: views, components, controllers widget-level coverage

## Lisensi

MIT © FenDoZ
