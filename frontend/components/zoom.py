"""Zoom control components, state management, and keyboard shortcut handlers for responsive readability."""

import flet as ft

DEFAULT_ZOOM = 1.0
MIN_ZOOM = 0.7
MAX_ZOOM = 1.8
ZOOM_STEP = 0.1

_current_zoom = DEFAULT_ZOOM


def get_current_zoom(page: ft.Page = None) -> float:
    """Returns the active zoom scale factor."""
    global _current_zoom
    if page and hasattr(page, "session"):
        try:
            stored = page.session.get("zoom_scale")
            if isinstance(stored, (int, float)):
                return float(stored)
        except Exception:
            pass
    return _current_zoom


def set_current_zoom(page: ft.Page, scale: float) -> None:
    """Updates the active zoom scale factor bounded between MIN_ZOOM and MAX_ZOOM."""
    global _current_zoom
    scale = max(MIN_ZOOM, min(MAX_ZOOM, round(scale, 2)))
    _current_zoom = scale
    if page and hasattr(page, "session"):
        try:
            page.session.set("zoom_scale", scale)
        except Exception:
            pass


def apply_zoom_to_active_view(page: ft.Page, scale: float) -> None:
    """Applies zoom scale transformation to the current top view container and adjusts layout padding."""
    set_current_zoom(page, scale)
    if not page or not hasattr(page, "views") or not page.views:
        return

    top_view = page.views[-1]
    if top_view.controls:
        root_container = top_view.controls[0]
        if isinstance(root_container, ft.Container):
            root_container.scale = ft.Scale(scale=scale, alignment=ft.alignment.top_center)
            extra_bottom = int(max(0.0, (scale - 1.0) * 800))
            root_container.padding = ft.padding.only(left=20, right=20, top=20, bottom=20 + extra_bottom)

    if hasattr(page, "session"):
        try:
            label = page.session.get("zoom_display_label")
            if label and hasattr(label, "value"):
                label.value = f"{int(round(scale * 100))}%"
        except Exception:
            pass

    try:
        page.update()
    except Exception:
        pass


def create_zoom_controls(page: ft.Page) -> ft.Control:
    """Creates a sleek on-screen zoom toolbar with Zoom In, Zoom Out, and Reset buttons."""
    zoom_val = get_current_zoom(page)
    display_label = ft.Text(
        f"{int(round(zoom_val * 100))}%",
        size=12,
        weight=ft.FontWeight.BOLD,
        color=ft.colors.PRIMARY,
    )
    if hasattr(page, "session"):
        try:
            page.session.set("zoom_display_label", display_label)
        except Exception:
            pass

    def on_zoom_in(e: ft.ControlEvent) -> None:
        curr = get_current_zoom(page)
        apply_zoom_to_active_view(page, curr + ZOOM_STEP)

    def on_zoom_out(e: ft.ControlEvent) -> None:
        curr = get_current_zoom(page)
        apply_zoom_to_active_view(page, curr - ZOOM_STEP)

    def on_zoom_reset(e: ft.ControlEvent) -> None:
        apply_zoom_to_active_view(page, DEFAULT_ZOOM)

    return ft.Container(
        content=ft.Row([
            ft.IconButton(
                icon=ft.icons.REMOVE,
                tooltip="Zoom Out (Ctrl -)",
                icon_size=16,
                on_click=on_zoom_out,
            ),
            display_label,
            ft.IconButton(
                icon=ft.icons.ADD,
                tooltip="Zoom In (Ctrl +)",
                icon_size=16,
                on_click=on_zoom_in,
            ),
            ft.IconButton(
                icon=ft.icons.RESTART_ALT,
                tooltip="Reset Zoom (Ctrl 0)",
                icon_size=16,
                on_click=on_zoom_reset,
            ),
        ], spacing=2, alignment=ft.MainAxisAlignment.CENTER),
        border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
        border_radius=20,
        padding=ft.padding.symmetric(horizontal=6, vertical=2),
        bgcolor=ft.colors.SURFACE_VARIANT,
    )


def handle_keyboard_zoom(page: ft.Page, e: ft.KeyboardEvent) -> None:
    """Handles global Ctrl/Meta zoom key bindings."""
    if not (e.ctrl or e.meta):
        return

    curr = get_current_zoom(page)
    if e.key in ("+", "=", "Add"):
        apply_zoom_to_active_view(page, curr + ZOOM_STEP)
    elif e.key in ("-", "_", "Subtract"):
        apply_zoom_to_active_view(page, curr - ZOOM_STEP)
    elif e.key in ("0", "Digit0", "Numpad0"):
        apply_zoom_to_active_view(page, DEFAULT_ZOOM)
