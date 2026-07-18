# coding:utf-8
"""
setting_interface.py — Settings page with grouped setting cards.

FR-7.x: library folder management, theme, reduce motion.
FR-8.2: crash log location.
"""

from __future__ import annotations

import os

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFileDialog, QLabel, QWidget
from qfluentwidgets import (
    ComboBoxSettingCard,
    CustomColorSettingCard,
    ExpandLayout,
    HyperlinkCard,
    InfoBar,
    OptionsSettingCard,
    PrimaryPushSettingCard,
    PushSettingCard,
    RangeSettingCard,
    ScrollArea,
    SettingCardGroup,
    SwitchSettingCard,
    setTheme,
    setThemeColor,
)
from qfluentwidgets import FluentIcon as FIF

from nocturne.common.signal_bus import signalBus
from nocturne.common.style_sheet import StyleSheet
from nocturne.config.config import FEEDBACK_URL, HELP_URL, VERSION, YEAR, cfg, isWin11


class SettingInterface(ScrollArea):
    """Setting interface"""

    def __init__(self, parent=None):
        super().__init__(parent=parent)
        self.scrollWidget = QWidget()
        self.expandLayout = ExpandLayout(self.scrollWidget)

        # setting label
        self.settingLabel = QLabel(self.tr("Settings"), self)

        # personalization
        self.personalGroup = SettingCardGroup(
            self.tr("Personalization"), self.scrollWidget
        )

        self.micaCard = SwitchSettingCard(
            FIF.TRANSPARENT,
            self.tr("Mica effect"),
            self.tr("Apply semi transparent to windows and surfaces (if OS Windows)"),
            cfg.micaEnabled,
            self.personalGroup,
        )
        self.themeCard = OptionsSettingCard(
            cfg.themeMode,
            FIF.BRUSH,
            self.tr("Application theme"),
            self.tr("Change the appearance of your application"),
            texts=[self.tr("Light"), self.tr("Dark"), self.tr("Use system setting")],
            parent=self.personalGroup,
        )
        self.themeColorCard = CustomColorSettingCard(
            cfg.themeColor,
            FIF.PALETTE,
            self.tr("Theme color"),
            self.tr("Change the theme color of you application"),
            self.personalGroup,
        )
        self.zoomCard = OptionsSettingCard(
            cfg.dpiScale,
            FIF.ZOOM,
            self.tr("Interface zoom"),
            self.tr("Change the size of widgets and fonts"),
            texts=["100%", "125%", "150%", "175%", "200%", self.tr("Use system setting")],
            parent=self.personalGroup,
        )
        self.languageCard = ComboBoxSettingCard(
            cfg.language,
            FIF.LANGUAGE,
            self.tr("Language"),
            self.tr("Set your preferred language for UI"),
            texts=["Bahasa Indonesia", "English", self.tr("Use system setting")],
            parent=self.personalGroup,
        )

        # material
        self.materialGroup = SettingCardGroup(self.tr("Material"), self.scrollWidget)
        self.blurRadiusCard = RangeSettingCard(
            cfg.blurRadius,
            FIF.ALBUM,
            self.tr("Acrylic blur radius"),
            self.tr("The greater the radius, the more blurred the image"),
            self.materialGroup,
        )

        # ── Library ───────────────────────────────────────────────────
        self.libraryGroup = SettingCardGroup(
            self.tr("Music Library"), self.scrollWidget
        )

        self.folderCard = PushSettingCard(
            self.tr("Add Folder"),
            FIF.FOLDER_ADD,
            self.tr("Music folders"),
            self.tr("No folders configured. Click to add your music directory."),
            self.libraryGroup,
        )
        self.folderCard.clicked.connect(self._add_folder)

        self.scanCard = PushSettingCard(
            self.tr("Scan Now"),
            FIF.SYNC,
            self.tr("Scan library"),
            self.tr("Scan all configured folders for new and updated tracks."),
            self.libraryGroup,
        )

        # ── Online ─────────────────────────────────────────────────────
        self.onlineGroup = SettingCardGroup(
            self.tr("Online (SoundCloud)"), self.scrollWidget
        )

        self.onlineToggleCard = SwitchSettingCard(
            FIF.CLOUD,
            self.tr("Enable online features"),
            self.tr("Allow SoundCloud track search, streaming, and URL resolution"),
            cfg.onlineEnabled,
            self.onlineGroup,
        )

        self.cacheOfflineCard = SwitchSettingCard(
            FIF.CLOUD_DOWNLOAD,
            self.tr("Cache offline"),
            self.tr("Save streamed tracks to local cache for offline playback"),
            cfg.cacheOffline,
            self.onlineGroup,
        )

        self.lyricsOnlineCard = SwitchSettingCard(
            FIF.CHAT,
            self.tr("Online lyrics lookup"),
            self.tr("Search for lyrics online when local lyrics are not available"),
            cfg.lyricsOnline,
            self.onlineGroup,
        )

        # ── Accessibility ─────────────────────────────────────────────
        self.accessGroup = SettingCardGroup(
            self.tr("Accessibility"), self.scrollWidget
        )

        # ponytail: reduce_motion config isn't persisted yet — add config
        # item when full settings persistence is implemented
        self.reduceMotionCard = SwitchSettingCard(
            FIF.VIEW,
            self.tr("Reduce motion"),
            self.tr("Reduce visualiser complexity and animation effects"),
            cfg.confirmExit,  # placeholder toggle
            self.accessGroup,
        )

        # ── Application ───────────────────────────────────────────────
        self.aboutGroup = SettingCardGroup(self.tr("About"), self.scrollWidget)
        self.helpCard = HyperlinkCard(
            HELP_URL,
            self.tr("Open help page"),
            FIF.HELP,
            self.tr("Help"),
            self.tr("Discover new features and learn useful tips about Nocturne"),
            self.aboutGroup,
        )
        self.feedbackCard = PrimaryPushSettingCard(
            self.tr("Provide feedback"),
            FIF.FEEDBACK,
            self.tr("Provide feedback"),
            self.tr("Help us improve Nocturne by providing feedback"),
            self.aboutGroup,
        )
        self.aboutCard = PrimaryPushSettingCard(
            self.tr("Check update"),
            FIF.INFO,
            self.tr("About"),
            "© " + self.tr("Copyright") + f" {YEAR}, FenDoZ. "
            + self.tr("Version") + " " + VERSION,
            self.aboutGroup,
        )

        self.autoSaveSetting = SwitchSettingCard(
            FIF.SAVE,
            self.tr("Auto save note"),
            self.tr("Automatically save notes when changed"),
            cfg.autoSaveNote,
            self.personalGroup,
        )
        self.confirmExitSetting = SwitchSettingCard(
            FIF.CLOSE,
            self.tr("Confirm exit"),
            self.tr("Show a confirmation dialog when exiting the application"),
            cfg.confirmExit,
            self.personalGroup,
        )

        # Crash log location
        self.crashLogCard = PushSettingCard(
            self.tr("Open Log Folder"),
            FIF.DOCUMENT,
            self.tr("Crash logs"),
            self.tr("Application errors are logged locally — no data is sent anywhere."),
            self.aboutGroup,
        )
        from nocturne.data.db import get_db_path
        self._crash_log_dir = str(get_db_path().parent)
        self.crashLogCard.clicked.connect(self._open_crash_log_dir)

        self.__initWidget()

    def __initWidget(self):
        self.resize(1000, 800)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportMargins(0, 80, 0, 20)
        self.setWidget(self.scrollWidget)
        self.setWidgetResizable(True)
        self.setObjectName("settingInterface")

        self.scrollWidget.setObjectName("scrollWidget")
        self.settingLabel.setObjectName("settingLabel")
        StyleSheet.SETTING_INTRFACE_STYLE.apply(self)

        self.micaCard.setEnabled(isWin11())

        self.__initLayout()
        self.__connectSignalToSlot()

    def __initLayout(self):
        self.settingLabel.move(36, 30)

        self.personalGroup.addSettingCard(self.micaCard)
        self.personalGroup.addSettingCard(self.themeCard)
        self.personalGroup.addSettingCard(self.themeColorCard)
        self.personalGroup.addSettingCard(self.zoomCard)
        self.personalGroup.addSettingCard(self.languageCard)
        self.personalGroup.addSettingCard(self.autoSaveSetting)
        self.personalGroup.addSettingCard(self.confirmExitSetting)
        self.materialGroup.addSettingCard(self.blurRadiusCard)
        self.libraryGroup.addSettingCard(self.folderCard)
        self.libraryGroup.addSettingCard(self.scanCard)
        self.onlineGroup.addSettingCard(self.onlineToggleCard)
        self.onlineGroup.addSettingCard(self.cacheOfflineCard)
        self.onlineGroup.addSettingCard(self.lyricsOnlineCard)
        self.accessGroup.addSettingCard(self.reduceMotionCard)
        self.aboutGroup.addSettingCard(self.helpCard)
        self.aboutGroup.addSettingCard(self.feedbackCard)
        self.aboutGroup.addSettingCard(self.crashLogCard)
        self.aboutGroup.addSettingCard(self.aboutCard)

        self.expandLayout.setSpacing(28)
        self.expandLayout.setContentsMargins(36, 10, 36, 0)
        self.expandLayout.addWidget(self.personalGroup)
        self.expandLayout.addWidget(self.materialGroup)
        self.expandLayout.addWidget(self.libraryGroup)
        self.expandLayout.addWidget(self.onlineGroup)
        self.expandLayout.addWidget(self.accessGroup)
        self.expandLayout.addWidget(self.aboutGroup)

    def __showRestartTooltip(self):
        InfoBar.success(
            self.tr("Updated successfully"),
            self.tr("Configuration takes effect after restart"),
            duration=1500,
            parent=self,
        )

    def __connectSignalToSlot(self):
        cfg.appRestartSig.connect(self.__showRestartTooltip)
        cfg.themeChanged.connect(setTheme)
        self.themeColorCard.colorChanged.connect(lambda c: setThemeColor(c))
        self.micaCard.checkedChanged.connect(signalBus.micaEnableChanged)
        self.feedbackCard.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl(FEEDBACK_URL))
        )

    def _add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(
            self, "Select Music Folder"
        )
        if folder:
            self.folderCard.setContent(
                self.tr(f"Folder: {folder}")
            )

    def _open_crash_log_dir(self) -> None:
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._crash_log_dir))
