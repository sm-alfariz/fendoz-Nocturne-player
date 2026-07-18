# coding:utf-8
import sys
from unittest.mock import patch

import pytest
from PySide6.QtCore import QLocale

from src.config.config import (
    Config,
    Language,
    LanguageSerializer,
    isWin11,
    cfg,
    YEAR,
    AUTHOR,
    VERSION,
    HELP_URL,
    REPO_URL,
    EXAMPLE_URL,
    FEEDBACK_URL,
    RELEASE_URL,
    ZH_SUPPORT_URL,
    EN_SUPPORT_URL,
)


class TestLanguage:
    def test_members(self):
        assert Language.INDONESIA is not None
        assert Language.ENGLISH is not None
        assert Language.AUTO is not None
        assert len(Language) == 3

    def test_values_are_qlocale(self):
        for lang in Language:
            assert isinstance(lang.value, QLocale)


class TestLanguageSerializer:
    def setup_method(self):
        self.ser = LanguageSerializer()

    def test_serialize_indonesia(self):
        # QLocale(Indonesian, Indonesia).name() == "id_ID"
        assert self.ser.serialize(Language.INDONESIA) == "id_ID"

    def test_serialize_auto(self):
        assert self.ser.serialize(Language.AUTO) == "Auto"

    def test_deserialize_auto(self):
        assert self.ser.deserialize("Auto") is Language.AUTO

    def test_deserialize_roundtrip(self):
        # Roundtrip: serialize → deserialize yields same Language
        for lang in Language:
            if lang is Language.AUTO:
                continue
            serialized = self.ser.serialize(lang)
            deserialized = self.ser.deserialize(serialized)
            assert deserialized == lang

    def test_deserialize_invalid_raises(self):
        with pytest.raises(Exception):
            self.ser.deserialize("NonExistentLanguage")


class TestIsWin11:
    def test_returns_false_on_linux(self):
        # On Linux, sys.platform is 'linux', so isWin11() returns False
        assert isWin11() is False

    @pytest.mark.skipif(
        not hasattr(sys, "getwindowsversion"), reason="requires Windows"
    )
    @patch("src.config.config.sys.platform", "win32")
    @patch("src.config.config.sys.getwindowsversion")
    def test_win11_returns_true(self, mock_getwindowsversion):
        mock_getwindowsversion.return_value.build = 22000
        assert isWin11() is True

    @pytest.mark.skipif(
        not hasattr(sys, "getwindowsversion"), reason="requires Windows"
    )
    @patch("src.config.config.sys.platform", "win32")
    @patch("src.config.config.sys.getwindowsversion")
    def test_win10_returns_false(self, mock_getwindowsversion):
        mock_getwindowsversion.return_value.build = 19045
        assert isWin11() is False


class TestConfig:
    def test_has_expected_attributes(self):
        """Config class defines the expected config items."""
        assert hasattr(Config, "micaEnabled")
        assert hasattr(Config, "dpiScale")
        assert hasattr(Config, "language")
        assert hasattr(Config, "blurRadius")
        assert hasattr(Config, "autoSaveNote")
        assert hasattr(Config, "confirmExit")

    def test_cfg_singleton_theme_loaded_from_config_json(self):
        # config.json has ThemeMode=Auto, so after load it's Auto
        from qfluentwidgets import Theme

        assert cfg.themeMode.value == Theme.AUTO


class TestConstants:
    def test_year(self):
        assert isinstance(YEAR, int)
        assert YEAR > 2020

    def test_author(self):
        assert isinstance(AUTHOR, str)
        assert len(AUTHOR) > 0

    def test_version(self):
        assert isinstance(VERSION, str)
        assert len(VERSION) > 0

    def test_urls_are_non_empty_strings(self):
        urls = [HELP_URL, REPO_URL, EXAMPLE_URL, FEEDBACK_URL, RELEASE_URL, ZH_SUPPORT_URL, EN_SUPPORT_URL]
        for u in urls:
            assert isinstance(u, str)
            assert u.startswith("http")
