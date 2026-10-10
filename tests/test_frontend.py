"""Unit tests for Flet adaptive frontend views, theme configuration, and navigation components."""

from unittest.mock import MagicMock
import flet as ft
import pytest

from frontend.components.navigation import get_adaptive_nav, get_desktop_rail
from frontend.components.theme import get_app_theme
from frontend.main import main
from frontend.views.dashboard import dashboard_view
from frontend.views.diet import diet_view
from frontend.views.login import login_view
from frontend.views.settings import settings_view


class MockClientStorage:
    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    async def get_async(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value

    async def set_async(self, key, value):
        self.data[key] = value

    def remove(self, key):
        self.data.pop(key, None)

    async def remove_async(self, key):
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
    session_data = {}
    page.session = MagicMock()
    page.session.get = MagicMock(side_effect=lambda k: session_data.get(k))
    page.session.set = MagicMock(side_effect=lambda k, v: session_data.__setitem__(k, v))
    page.update = MagicMock()
    page.go = MagicMock()
    page.window = MagicMock()
    return page


def test_app_theme_configuration() -> None:
    theme = get_app_theme()
    assert isinstance(theme, ft.Theme)
    assert theme.use_material3 is True
    assert theme.color_scheme_seed == ft.colors.INDIGO


def test_adaptive_navigation_components(mock_page) -> None:
    nav_bar = get_adaptive_nav(mock_page, selected_index=0)
    assert isinstance(nav_bar, ft.NavigationBar)
    assert len(nav_bar.destinations) == 4
    assert nav_bar.selected_index == 0

    rail = get_desktop_rail(mock_page, selected_index=1)
    assert isinstance(rail, ft.NavigationRail)
    assert len(rail.destinations) == 4
    assert rail.selected_index == 1


def test_login_view_construction(mock_page) -> None:
    view = login_view(mock_page)
    assert isinstance(view, ft.View)
    assert view.route == "/"
    assert len(view.controls) > 0
    assert view.scroll == ft.ScrollMode.AUTO


def test_dashboard_view_construction(mock_page) -> None:
    view = dashboard_view(mock_page)
    assert isinstance(view, ft.View)
    assert view.route == "/dashboard"
    assert len(view.controls) >= 2
    assert view.scroll == ft.ScrollMode.AUTO


def test_dashboard_view_with_active_plan(mock_page) -> None:
    active_plan = {
        "target_calories_kcal": 2800,
        "target_protein_g": 190,
        "training_split": ["Day 1: Heavy Bench", "Day 2: Squat Volume"],
        "exercise_selection": [
            {"exercise": "Barbell Bench Press", "sets": 4, "reps": "6-8", "target_rpe": 8.5},
            {"exercise": "Barbell Back Squat", "sets": 3, "reps": "5-8", "target_rpe": 8.0},
        ],
    }
    mock_page.client_storage.set("active_regime_plan", active_plan)
    mock_page.client_storage.set("active_diet_plan", {"target_calories": 2800, "protein_g": 190, "fat_g": 75, "carbs_g": 340})
    mock_page.client_storage.set("completed_lifts", {"Barbell Bench Press": {"weight": 105.0, "reps": 6, "e1rm": 126.0}})
    mock_page.client_storage.set("daily_nutrition_logged", {"calories": 1400, "protein": 95})

    view = dashboard_view(mock_page)
    assert isinstance(view, ft.View)
    assert view.route == "/dashboard"
    assert len(view.controls) >= 2


def test_diet_view_construction(mock_page) -> None:
    view = diet_view(mock_page)
    assert isinstance(view, ft.View)
    assert view.route == "/diet"
    assert len(view.controls) >= 2
    assert view.scroll == ft.ScrollMode.AUTO


def test_settings_view_construction(mock_page) -> None:
    view = settings_view(mock_page)
    assert isinstance(view, ft.View)
    assert view.route == "/settings"
    assert len(view.controls) >= 2
    assert view.scroll == ft.ScrollMode.AUTO


def test_settings_view_with_cached_profile_and_active_plan(mock_page) -> None:
    mock_page.client_storage.set("user_profile", {
        "email": "champion@bodymaxxing.local",
        "age": 28,
        "height_cm": 185.0,
        "weight_kg": 88.0,
        "body_fat_pct": 12.5,
        "free_text_goals": "Peak powerlifting total",
    })
    mock_page.client_storage.set("is_new_user", True)

    view = settings_view(mock_page)
    assert isinstance(view, ft.View)
    assert view.route == "/settings"
    # Verify active plan was automatically synthesized into client storage
    cached = mock_page.client_storage.get("active_regime_plan")
    assert cached is not None
    assert "target_calories_kcal" in cached
    assert "exercise_selection" in cached



def test_main_page_initialization(mock_page) -> None:
    main(mock_page)
    assert mock_page.title == "BodyMaxxing - AI Fitness Progression"
    assert mock_page.theme_mode == ft.ThemeMode.SYSTEM
    assert mock_page.theme is not None
    assert mock_page.scroll == ft.ScrollMode.AUTO
    mock_page.go.assert_called_with("/")


def test_zoom_components_and_keyboard_handling(mock_page) -> None:
    from frontend.components.zoom import (
        create_zoom_controls,
        get_current_zoom,
        set_current_zoom,
        handle_keyboard_zoom,
        DEFAULT_ZOOM,
    )
    # Test zoom control UI creation
    controls = create_zoom_controls(mock_page)
    assert isinstance(controls, ft.Container)

    # Test setting and getting zoom scale
    set_current_zoom(mock_page, 1.2)
    assert get_current_zoom(mock_page) == 1.2

    # Test keyboard events: Ctrl + '+'
    event_zoom_in = MagicMock(spec=ft.KeyboardEvent)
    event_zoom_in.ctrl = True
    event_zoom_in.meta = False
    event_zoom_in.key = "+"
    handle_keyboard_zoom(mock_page, event_zoom_in)
    assert round(get_current_zoom(mock_page), 2) == 1.3

    # Test keyboard events: Ctrl + '0' (reset)
    event_reset = MagicMock(spec=ft.KeyboardEvent)
    event_reset.ctrl = True
    event_reset.meta = False
    event_reset.key = "0"
    handle_keyboard_zoom(mock_page, event_reset)
    assert get_current_zoom(mock_page) == DEFAULT_ZOOM
