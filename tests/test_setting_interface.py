# coding:utf-8
from src.config.config import HELP_URL, cfg, VERSION, YEAR
from src.views.setting_interface import SettingInterface


class TestSettingInterface:
    def test_construction(self, qtbot):
        si = SettingInterface()
        qtbot.addWidget(si)

        assert si.objectName() == "settingInterface"
        assert si.widget() is si.scrollWidget
        assert si.horizontalScrollBarPolicy().name == "ScrollBarAlwaysOff"

    def test_has_setting_label(self, qtbot):
        si = SettingInterface()
        qtbot.addWidget(si)

        assert si.settingLabel.text() == "Settings"

    def test_has_personalization_cards(self, qtbot):
        si = SettingInterface()
        qtbot.addWidget(si)

        assert si.micaCard is not None
        assert si.themeCard is not None
        assert si.themeColorCard is not None
        assert si.zoomCard is not None
        assert si.languageCard is not None
        assert si.autoSaveSetting is not None
        assert si.confirmExitSetting is not None

    def test_has_material_group(self, qtbot):
        si = SettingInterface()
        qtbot.addWidget(si)

        assert si.blurRadiusCard is not None

    def test_has_about_group(self, qtbot):
        si = SettingInterface()
        qtbot.addWidget(si)

        assert si.helpCard is not None
        assert si.feedbackCard is not None
        assert si.aboutCard is not None

    def test_mica_card_disabled_on_linux(self, qtbot):
        si = SettingInterface()
        qtbot.addWidget(si)

        # On Linux, isWin11() is False → micaCard should be disabled
        assert si.micaCard.isEnabled() is False

    def test_auto_save_setting_bound_to_cfg(self, qtbot):
        si = SettingInterface()
        qtbot.addWidget(si)

        assert si.autoSaveSetting.configItem is cfg.autoSaveNote

    def test_confirm_exit_setting_bound_to_cfg(self, qtbot):
        si = SettingInterface()
        qtbot.addWidget(si)

        assert si.confirmExitSetting.configItem is cfg.confirmExit

    def test_theme_card_bound_to_cfg(self, qtbot):
        si = SettingInterface()
        qtbot.addWidget(si)

        assert si.themeCard.configItem is cfg.themeMode

    def test_zoom_card_bound_to_cfg(self, qtbot):
        si = SettingInterface()
        qtbot.addWidget(si)

        assert si.zoomCard.configItem is cfg.dpiScale

    def test_blur_radius_card_bound_to_cfg(self, qtbot):
        si = SettingInterface()
        qtbot.addWidget(si)

        assert si.blurRadiusCard.configItem is cfg.blurRadius

    def test_language_card_bound_to_cfg(self, qtbot):
        si = SettingInterface()
        qtbot.addWidget(si)

        assert si.languageCard.configItem is cfg.language

    def test_help_card_has_url(self, qtbot):
        si = SettingInterface()
        qtbot.addWidget(si)

        assert si.helpCard.linkButton.url.toString() == HELP_URL

    def test_about_card_contains_version(self, qtbot):
        si = SettingInterface()
        qtbot.addWidget(si)

        assert VERSION in si.aboutCard.contentLabel.text()

    def test_about_card_contains_year(self, qtbot):
        si = SettingInterface()
        qtbot.addWidget(si)

        assert str(YEAR) in si.aboutCard.contentLabel.text()
