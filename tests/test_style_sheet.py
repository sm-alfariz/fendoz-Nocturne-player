# coding:utf-8
from src.common.style_sheet import StyleSheet


class TestStyleSheet:
    def test_has_four_members(self):
        assert len(StyleSheet) == 4

    def test_member_values(self):
        assert StyleSheet.LINK_CARD.value == "link_card"
        assert StyleSheet.SAMPLE_CARD.value == "sample_card"
        assert StyleSheet.HOME_WIDGET_STYLE.value == "home_interface"
        assert StyleSheet.SETTING_INTRFACE_STYLE.value == "setting_interface"

    def test_path_returns_string(self):
        path = StyleSheet.LINK_CARD.path()
        assert isinstance(path, str)
        assert path.endswith("/link_card.qss")

    def test_path_with_explicit_theme(self):
        from qfluentwidgets import Theme

        path = StyleSheet.LINK_CARD.path(theme=Theme.DARK)
        assert "dark" in path
        assert path.endswith("/link_card.qss")

        path_light = StyleSheet.LINK_CARD.path(theme=Theme.LIGHT)
        assert "light" in path_light
        assert path_light.endswith("/link_card.qss")
