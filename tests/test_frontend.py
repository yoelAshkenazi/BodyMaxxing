"""Unit tests for Flet adaptive frontend views, theme configuration, and navigation components."""

from unittest.mock import MagicMock
import flet as ft
import pytest

from frontend.components.navigation import get_adaptive_nav, get_desktop_rail
from frontend.components.theme import get_app_theme
from frontend.main import main
from frontend.views.dashboard import dashboard_view
from frontend.views.login import login_view
from frontend.views.settings import settings_view


class MockClientStorage:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value

    def remove(self, key):
        self.data.pop(key, None)


@pytest.fixture
def mock_page():
    page = MagicMock(spec=ft.Page)
    page.title = ""
    page.theme_mode = None
    page.theme = None
    page.views = []
    page.route = "/"
    page.client_storage = MockClientStorage()
    page.update = MagicMock()
    page.go = MagicMock()
    return page


def test_app_theme_configuration() -> None:
    theme = get_app_theme()
    assert isinstance(theme, ft.Theme)
    assert theme.use_material3 is True
    assert theme.color_scheme_seed == ft.colors.INDIGO


def test_adaptive_navigation_components(mock_page) -> None:
    nav_bar = get_adaptive_nav(mock_page, selected_index=0)
    assert isinstance(nav_bar, ft.NavigationBar)
    assert len(nav_bar.destinations) == 3
    assert nav_bar.selected_index == 0

    rail = get_desktop_rail(mock_page, selected_index=1)
    assert isinstance(rail, ft.NavigationRail)
    assert len(rail.destinations) == 3
    assert rail.selected_index == 1


def test_login_view_construction(mock_page) -> None:
    view = login_view(mock_page)
    assert isinstance(view, ft.View)
    assert view.route == "/"
    assert len(view.controls) > 0


def test_dashboard_view_construction(mock_page) -> None:
    view = dashboard_view(mock_page)
    assert isinstance(view, ft.View)
    assert view.route == "/dashboard"
    assert len(view.controls) >= 2


def test_settings_view_construction(mock_page) -> None:
    view = settings_view(mock_page)
    assert isinstance(view, ft.View)
    assert view.route == "/settings"
    assert len(view.controls) >= 2


def test_main_page_initialization(mock_page) -> None:
    main(mock_page)
    assert mock_page.title == "BodyMaxxing - AI Fitness Progression"
    assert mock_page.theme_mode == ft.ThemeMode.SYSTEM
    assert mock_page.theme is not None
    mock_page.go.assert_called_with("/")
