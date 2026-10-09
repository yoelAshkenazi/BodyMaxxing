import sys
from pathlib import Path

# Ensure workspace root and frontend folder are discoverable in sys.path
_current_dir = Path(__file__).resolve().parent
_workspace_root = _current_dir.parent
if str(_workspace_root) not in sys.path:
    sys.path.insert(0, str(_workspace_root))
if str(_current_dir) not in sys.path:
    sys.path.insert(0, str(_current_dir))

import flet as ft

try:
    from frontend.components.theme import get_app_theme
    from frontend.views.dashboard import dashboard_view
    from frontend.views.login import login_view
    from frontend.views.settings import settings_view
except ModuleNotFoundError:
    from components.theme import get_app_theme
    from views.dashboard import dashboard_view
    from views.login import login_view
    from views.settings import settings_view


def main(page: ft.Page) -> None:
    """Application entry point configuring OS theme syncing, routing, and view stack."""
    page.title = "BodyMaxxing - AI Fitness Progression"

    # Adaptive theming based on OS settings
    page.theme_mode = ft.ThemeMode.SYSTEM
    page.theme = get_app_theme()

    def route_change(e: ft.RouteChangeEvent) -> None:
        page.views.clear()
        route = page.route or "/"

        if route == "/":
            page.views.append(login_view(page))
        elif route == "/dashboard":
            page.views.append(dashboard_view(page))
        elif route == "/settings":
            page.views.append(settings_view(page))
        else:
            page.views.append(login_view(page))

        page.update()

    def view_pop(e: ft.ViewPopEvent) -> None:
        if len(page.views) > 1:
            page.views.pop()
            top_view = page.views[-1]
            page.go(top_view.route)

    page.on_route_change = route_change
    page.on_view_pop = view_pop

    # Route to dashboard if authenticated token exists, else login
    token = page.client_storage.get("token")
    if token:
        page.go("/dashboard")
    else:
        page.go("/")


if __name__ == "__main__":
    # Target enables desktop rendering; Pyodide integration handles WebAssembly deployment
    ft.app(target=main)
