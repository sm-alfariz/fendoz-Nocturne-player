# coding:utf-8
"""
tag_editor.py — Modal dialog for editing a single MP3's ID3 tags.
Opens a file via mutagen.ID3, reads/writes title, artist, album, genre, cover art.
Cover is processed via PIL: center-crop square → resize 600×600 → JPEG.
"""

from __future__ import annotations

import os
import io
from typing import Optional

from PIL import Image
from mutagen.id3 import ID3, APIC, TPE1, TALB, TCON, TIT2, ID3NoHeaderError

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QLabel,
    QPushButton,
    QFileDialog,
    QDialogButtonBox,
    QMessageBox,
)

from nocturne.ui.theme.tokens import Color

COVER_SIZE = (600, 600)


def read_mp3_tags(file_path: str) -> dict:
    """Read ID3 tags + cover bytes from an MP3 file."""
    result: dict = {}
    try:
        tags = ID3(file_path)
    except ID3NoHeaderError:
        return result

    if tags.get("TIT2"):
        result["title"] = str(tags["TIT2"])
    if tags.get("TPE1"):
        result["artist"] = str(tags["TPE1"])
    if tags.get("TALB"):
        result["album"] = str(tags["TALB"])
    if tags.get("TCON"):
        result["genre"] = str(tags["TCON"])

    apic = tags.get("APIC:") or tags.get("APIC:Cover")
    if apic and hasattr(apic, "data"):
        result["cover_data"] = apic.data
        result["cover_mime"] = apic.mime

    return result


def process_cover(image_path: str) -> bytes:
    """
    Open image → RGB → center-crop square → resize 600×600 → return JPEG bytes.
    """
    with Image.open(image_path) as img:
        img = img.convert("RGB")
        w, h = img.size
        dim = min(w, h)
        left = (w - dim) / 2
        top = (h - dim) / 2
        cropped = img.crop((left, top, left + dim, top + dim))
        resized = cropped.resize(COVER_SIZE, Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format="JPEG", quality=85)
        return buf.getvalue()


def write_mp3_tags(
    file_path: str,
    title: str = "",
    artist: str = "",
    album: str = "",
    genre: str = "",
    cover_bytes: Optional[bytes] = None,
) -> None:
    """Write ID3v2.3 tags to an MP3 file."""
    try:
        tags = ID3(file_path)
    except ID3NoHeaderError:
        tags = ID3()

    tags.add(TIT2(encoding=3, text=title or "Unknown"))
    tags.add(TPE1(encoding=3, text=artist or ""))
    tags.add(TALB(encoding=3, text=album or ""))
    tags.add(TCON(encoding=3, text=genre or ""))

    if cover_bytes is not None:
        tags.delall("APIC")
        tags.add(
            APIC(
                encoding=3,
                mime="image/jpeg",
                type=3,
                desc="Cover",
                data=cover_bytes,
            )
        )

    tags.save(file_path, v2_version=3)


def _pixmap_from_bytes(data: bytes) -> Optional[QPixmap]:
    p = QPixmap()
    if p.loadFromData(data):
        return p
    return None


class TagEditorDialog(QDialog):
    """Modal dialog to edit ID3 tags of a single MP3 file."""

    def __init__(self, file_path: str, parent=None):
        super().__init__(parent)
        self._file_path = file_path
        self._cover_bytes: Optional[bytes] = None
        self._current_cover_data: Optional[bytes] = None

        self.setWindowTitle(f"Edit Tags — {os.path.basename(file_path)}")
        self.setMinimumWidth(420)
        self.setStyleSheet(f"""
            QDialog {{
                background:{Color.BACKGROUND};
                color:{Color.TEXT_PRIMARY};
            }}
            QLabel {{ color:{Color.TEXT_PRIMARY}; }}
            QLineEdit {{
                background:{Color.CARD};
                border:1px solid {Color.BORDER};
                border-radius:6px;
                padding:6px 10px;
                color:{Color.TEXT_PRIMARY};
                font-size:13px;
            }}
            QLineEdit:focus {{
                border-color:{Color.ACCENT};
            }}
            QPushButton {{
                background:{Color.CARD};
                border:1px solid {Color.BORDER};
                border-radius:6px;
                padding:6px 14px;
                color:{Color.TEXT_PRIMARY};
                font-size:13px;
            }}
            QPushButton:hover {{
                background:{Color.CARD_SOFT};
                border-color:{Color.ACCENT};
            }}
        """)

        self._load_current_tags()
        self._build_ui()

    # ── tag loading ────────────────────────────────────────────────────

    def _load_current_tags(self) -> None:
        tags = read_mp3_tags(self._file_path)
        self._current_title = tags.get("title", "")
        self._current_artist = tags.get("artist", "")
        self._current_album = tags.get("album", "")
        self._current_genre = tags.get("genre", "")
        self._current_cover_data = tags.get("cover_data")
        self._cover_bytes = self._current_cover_data  # initial = unchanged

    # ── UI build ───────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self._title_edit = QLineEdit(self._current_title)
        self._artist_edit = QLineEdit(self._current_artist)
        self._album_edit = QLineEdit(self._current_album)
        self._genre_edit = QLineEdit(self._current_genre)

        form.addRow("Title:", self._title_edit)
        form.addRow("Artist:", self._artist_edit)
        form.addRow("Album:", self._album_edit)
        form.addRow("Genre:", self._genre_edit)
        layout.addLayout(form)

        # ── Cover section ──────────────────────────────────────────────
        cover_label = QLabel("Cover Art:")
        layout.addWidget(cover_label)

        cover_row = QHBoxLayout()
        cover_row.setSpacing(12)

        self._cover_preview = QLabel()
        self._cover_preview.setFixedSize(120, 120)
        self._cover_preview.setAlignment(Qt.AlignCenter)
        self._cover_preview.setStyleSheet(
            f"background:{Color.CARD};border:1px solid {Color.BORDER};"
            f"border-radius:8px;"
        )
        self._update_cover_preview()
        cover_row.addWidget(self._cover_preview)

        cover_btn_col = QVBoxLayout()
        cover_btn_col.setSpacing(6)
        self._change_cover_btn = QPushButton("Change Cover…")
        self._change_cover_btn.clicked.connect(self._pick_cover)
        self._remove_cover_btn = QPushButton("Remove Cover")
        self._remove_cover_btn.clicked.connect(self._remove_cover)
        cover_btn_col.addWidget(self._change_cover_btn)
        cover_btn_col.addWidget(self._remove_cover_btn)
        cover_btn_col.addStretch()
        cover_row.addLayout(cover_btn_col)
        cover_row.addStretch()
        layout.addLayout(cover_row)

        # ── Buttons ────────────────────────────────────────────────────
        btn_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(self._on_save)
        btn_box.rejected.connect(self.reject)
        btn_box.setStyleSheet(
            f"QPushButton{{min-width:80px;padding:7px 18px;}}"
            f"QPushButton[text='Save']{{background:{Color.ACCENT};color:#fff;border:none;}}"
        )
        layout.addSpacing(8)
        layout.addWidget(btn_box)

    def _update_cover_preview(self) -> None:
        if self._cover_bytes:
            px = _pixmap_from_bytes(self._cover_bytes)
            if px:
                self._cover_preview.setPixmap(
                    px.scaled(118, 118, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                )
                return
        self._cover_preview.setText("No cover")
        self._cover_preview.setStyleSheet(
            f"background:{Color.CARD};border:1px solid {Color.BORDER};"
            f"border-radius:8px;color:{Color.TEXT_DIM};font-size:12px;"
        )

    # ── Cover actions ──────────────────────────────────────────────────

    def _pick_cover(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Cover Image",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp *.gif)",
        )
        if not path:
            return
        try:
            self._cover_bytes = process_cover(path)
            self._update_cover_preview()
        except Exception as exc:
            QMessageBox.warning(self, "Error", f"Failed to process image:\n{exc}")

    def _remove_cover(self) -> None:
        self._cover_bytes = None
        self._update_cover_preview()

    # ── Save ───────────────────────────────────────────────────────────

    def _on_save(self) -> None:
        title = self._title_edit.text().strip()
        artist = self._artist_edit.text().strip()
        album = self._album_edit.text().strip()
        genre = self._genre_edit.text().strip()

        try:
            write_mp3_tags(
                self._file_path,
                title=title,
                artist=artist,
                album=album,
                genre=genre,
                cover_bytes=self._cover_bytes,
            )
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Failed to save tags:\n{exc}")

    # ── Query helpers ──────────────────────────────────────────────────

    @property
    def edited_title(self) -> str:
        return self._title_edit.text().strip()

    @property
    def edited_artist(self) -> str:
        return self._artist_edit.text().strip()

    @property
    def cover_changed(self) -> bool:
        """True if cover data differs from what was read from the file."""
        return self._cover_bytes is not self._current_cover_data
