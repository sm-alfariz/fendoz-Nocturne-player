# coding:utf-8
"""Test icon_utils.py — pixmap/icon caching, artwork cache."""

from __future__ import annotations

from PySide6.QtGui import QPixmap

from nocturne.ui import icon_utils as iu


class TestPixmap:
    def test_pixmap_returns_non_null(self, qapp) -> None:
        pm = iu.pixmap("play.png")
        assert pm is not None
        assert not pm.isNull()

    def test_pixmap_caches(self, qapp) -> None:
        n = len(iu._cache)
        _ = iu.pixmap("play.png")
        assert len(iu._cache) == n  # already cached from previous test

    def test_pixmap_scaled(self, qapp) -> None:
        pm = iu.pixmap_scaled("play.png", 32, 32)
        assert pm is not None
        assert not pm.isNull()
        assert pm.width() == 32


class TestIcon:
    def test_icon_returns_non_null(self, qapp) -> None:
        ico = iu.icon("play.png")
        assert ico is not None

    def test_icon_caches(self, qapp) -> None:
        n = len(iu._icon_cache)
        _ = iu.icon("play.png")
        assert len(iu._icon_cache) == n  # already cached


class TestArtworkCache:
    def test_artwork_pixmap_caches(self, qapp) -> None:
        iu._artwork_cache.clear()
        blob = b""
        # Empty blob -> None, not cached
        result = iu.artwork_pixmap(1, blob, 140)
        assert result is None
        assert (1, 140) not in iu._artwork_cache

    def test_artwork_pixmap_caches_result(self, qapp) -> None:
        iu._artwork_cache.clear()
        # Use a valid small PNG blob
        import struct
        import zlib

        def _make_png(w: int, h: int) -> bytes:
            raw = b""
            for y in range(h):
                raw += b"\x00" + b"\xff\x00\x00" * w
            def _chunk(ctype: bytes, data: bytes) -> bytes:
                c = ctype + data
                return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
            ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
            return (
                b"\x89PNG\r\n\x1a\n"
                + _chunk(b"IHDR", ihdr)
                + _chunk(b"IDAT", zlib.compress(raw))
                + _chunk(b"IEND", b"")
            )

        blob = _make_png(10, 10)
        px = iu.artwork_pixmap(2, blob, 100)
        assert px is not None
        assert (2, 100) in iu._artwork_cache

        # Second call returns cached
        px2 = iu.artwork_pixmap(2, blob, 100)
        assert px2 is px  # same object from cache

    def test_invalidate_artwork_cache(self, qapp) -> None:
        iu._artwork_cache.clear()
        iu.artwork_pixmap(1, b"", 100)  # does nothing with empty but covers nil case
        # Cache a result for two sizes of album 3
        iu._artwork_cache[(3, 140)] = QPixmap()
        iu._artwork_cache[(3, 300)] = QPixmap()
        iu._artwork_cache[(4, 140)] = QPixmap()
        assert len(iu._artwork_cache) == 3
        iu.invalidate_artwork_cache(3)
        assert len(iu._artwork_cache) == 1
        assert (4, 140) in iu._artwork_cache
