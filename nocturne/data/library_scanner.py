# coding:utf-8
"""
library_scanner.py — Incremental folder scanner with metadata extraction.

Uses mutagen for ID3/Vorbis tag reading.  Skips files whose mtime
hasn't changed since the last scan.  Runs in a QThread so UI stays
responsive (FR-1.1–1.2, FR-5.5).
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import Optional

from mutagen import File as MutagenFile

from nocturne.data.models import Track

logger = logging.getLogger(__name__)


class ScanSignals:
    """QThread-compatible signals via plain callbacks (for QThread use, wrap)."""

    def __init__(self) -> None:
        self.progress = None  # callable(current, total)
        self.finished = None  # callable(new_tracks, updated_tracks)


class LibraryScanner:
    """Scan folders for supported audio files and extract metadata."""

    SUPPORTED_EXTENSIONS = {".mp3", ".flac", ".wav", ".ogg", ".m4a"}

    def __init__(self, db_conn: sqlite3.Connection) -> None:
        self._conn = db_conn
        self._signals = ScanSignals()

    @property
    def signals(self) -> ScanSignals:
        return self._signals

    def scan(self, folders: list[Path]) -> tuple[int, int]:
        """Incremental scan: add new tracks, update changed ones.

        Returns (new_tracks, updated_tracks).
        """
        new = updated = 0
        files = self._collect_files(folders)
        total = len(files)

        for idx, path in enumerate(files):
            if self._signals.progress:
                self._signals.progress(idx + 1, total)

            mtime = int(path.stat().st_mtime)
            existing = self._existing_track(path)

            if existing and existing.file_mtime == mtime:
                continue  # unchanged — skip

            meta = self._extract_metadata(path)
            if meta is None:
                continue

            if existing:
                self._update_track(existing.id, meta, mtime)
                updated += 1
            else:
                self._insert_track(meta, mtime)
                new += 1

        if self._signals.finished:
            self._signals.finished(new, updated)

        return new, updated

    def scan_async(self, folders: list[Path]) -> None:
        """Run scan in a background thread.  Connect to signals.progress
        and signals.finished for UI updates."""
        import threading
        t = threading.Thread(target=self.scan, args=(folders,), daemon=True)
        t.start()

    # ── Internals ─────────────────────────────────────────────────────

    @staticmethod
    def _parse_filename(stem: str) -> tuple[Optional[str], Optional[str]]:
        """Parse 'Artist - Title' from filename stem. Returns (artist, title)."""
        # Common separators: " - ", " – ", " — ", "_-_", "-"
        # Try " - " first (most common)
        for sep in [" - ", " – ", " — ", "_-_", "-"]:
            if sep in stem:
                parts = stem.split(sep, 1)
                if len(parts) == 2 and all(p.strip() for p in parts):
                    return parts[0].strip(), parts[1].strip()
        return None, None

    def _collect_files(self, folders: list[Path]) -> list[Path]:
        files: list[Path] = []
        for folder in folders:
            if not folder.is_dir():
                continue
            for root, _dirs, fnames in os.walk(str(folder)):
                for fname in fnames:
                    ext = Path(fname).suffix.lower()
                    if ext in self.SUPPORTED_EXTENSIONS:
                        files.append(Path(root) / fname)
        return files

    def _existing_track(self, path: Path) -> Optional[Track]:
        row = self._conn.execute(
            "SELECT * FROM tracks WHERE path = ?", (str(path),)
        ).fetchone()
        if row:
            self._conn.row_factory = sqlite3.Row
            return Track.from_row(row)
        return None

    def _extract_metadata(self, path: Path) -> Optional[dict]:
        """Extract {title, artist, album, duration_ms, artwork_blob, …}."""
        try:
            mf = MutagenFile(str(path))
            if mf is None:
                return None
        except Exception:
            logger.warning("Failed to open file: %s", path)
            return None

        def _tag(raw):
            """Extract text from an ID3 tag value (mutagen returns lists)."""
            if isinstance(raw, list):
                return str(raw[0]) if raw else ""
            return str(raw)

        tags = mf.tags or {}

        title = (
            _tag(tags.get("title", tags.get("TIT2", "")))
            if hasattr(tags, "get")
            else str(getattr(mf, "title", ""))
        ) or None

        artist = (
            _tag(tags.get("artist", tags.get("TPE1", "")))
            if hasattr(tags, "get")
            else str(getattr(mf, "artist", ""))
        ) or None

        # Fallback: parse "Artist - Title" from filename
        if not artist or not title:
            parsed_artist, parsed_title = self._parse_filename(path.stem)
            if not artist:
                artist = parsed_artist
            if not title:
                title = parsed_title

        title = title or path.stem

        album = (
            _tag(tags.get("album", tags.get("TALB", "")))
            if hasattr(tags, "get")
            else str(getattr(mf, "album", ""))
        ) or None

        duration_ms = int((mf.info.length if hasattr(mf, "info") and mf.info else 0) * 1000)

        artwork_blob = self._extract_artwork(mf)

        # SYLT lyrics (embedded) — extracted but stored via lyrics table
        lyrics_text = self._extract_sylt(mf)

        album_id = self._resolve_album(album, artist, artwork_blob)

        return {
            "path": str(path),
            "title": title,
            "artist": artist,
            "album_id": album_id,
            "duration_ms": duration_ms,
            "source_type": "local",
            "lyrics": lyrics_text,
        }

    def _extract_artwork(self, mf) -> Optional[bytes]:
        """Extract embedded artwork from the mutagen file."""
        try:
            for key in mf:
                if key.startswith("APIC"):
                    pic = mf[key]
                    if hasattr(pic, "data"):
                        return pic.data
            # FLAC / OGG
            for key in mf:
                if key.startswith("metadata_block_picture") or "cover" in key.lower():
                    pic = mf[key]
                    if hasattr(pic, "data"):
                        return pic.data
                    if hasattr(pic, "picture") and pic.picture:
                        return pic.picture[0].data
        except Exception:
            logger.warning("Failed to extract artwork")
        return None

    def _extract_sylt(self, mf) -> Optional[str]:
        """Extract synchronised lyrics (SYLT tag) as LRC-format text."""
        try:
            if "SYLT" in mf:
                sylt = mf["SYLT"]
                lines = []
                for line in sylt:
                    ts = int(line[0] * 1000)
                    text = line[2] if len(line) > 2 else ""
                    m, s = divmod(ts // 1000, 60)
                    ms = ts % 1000
                    lines.append(f"[{m:02d}:{s:02d}.{ms:03d}]{text}")
                return "\n".join(lines)
        except Exception:
            logger.warning("Failed to extract SYLT")
        return None

    def _resolve_album(self, album_title: Optional[str], artist: Optional[str], artwork_blob: Optional[bytes]) -> Optional[int]:
        """Find or create an album row.  Deduplicate on (title, artist)."""
        if not album_title:
            return None

        row = self._conn.execute(
            "SELECT id FROM albums WHERE title = ? AND (artist IS ? OR (artist IS NULL AND ? IS NULL))",
            (album_title, artist, artist),
        ).fetchone()

        if row:
            # Update artwork if we have one (prefer the one we just extracted)
            aid = row[0]
            if artwork_blob:
                self._conn.execute(
                    "UPDATE albums SET artwork_blob = ? WHERE id = ? AND artwork_blob IS NULL",
                    (artwork_blob, aid),
                )
                self._conn.commit()
            return aid

        cursor = self._conn.execute(
            "INSERT INTO albums (title, artist, artwork_blob) VALUES (?, ?, ?)",
            (album_title, artist, artwork_blob),
        )
        self._conn.commit()
        return cursor.lastrowid

    def _insert_track(self, meta: dict, mtime: int) -> None:
        self._conn.execute(
            """INSERT INTO tracks (path, title, artist, album_id, duration_ms, file_mtime, source_type)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (meta["path"], meta["title"], meta["artist"], meta["album_id"],
             meta["duration_ms"], mtime, meta["source_type"]),
        )
        self._conn.commit()

        # Insert lyrics if found
        if meta.get("lyrics"):
            track_id = self._conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            self._conn.execute(
                "INSERT OR REPLACE INTO lyrics (track_id, lrc_content) VALUES (?, ?)",
                (track_id, meta["lyrics"]),
            )
            self._conn.commit()

    def _update_track(self, track_id: int, meta: dict, mtime: int) -> None:
        self._conn.execute(
            """UPDATE tracks SET path=?, title=?, artist=?, album_id=?, duration_ms=?,
               file_mtime=?, source_type=? WHERE id=?""",
            (meta["path"], meta["title"], meta["artist"], meta["album_id"],
             meta["duration_ms"], mtime, meta["source_type"], track_id),
        )
        self._conn.commit()

        if meta.get("lyrics"):
            self._conn.execute(
                "INSERT OR REPLACE INTO lyrics (track_id, lrc_content) VALUES (?, ?)",
                (track_id, meta["lyrics"]),
            )
            self._conn.commit()


