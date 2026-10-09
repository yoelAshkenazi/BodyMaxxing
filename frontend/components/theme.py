"""Material Design 3 visual tokens, typography, and theme definitions for BodyMaxxing."""

import flet as ft


def get_app_theme() -> ft.Theme:
    """Returns the primary Material Design 3 theme configuration."""
    return ft.Theme(
        color_scheme_seed=ft.colors.INDIGO,
        use_material3=True,
    )


# Common container styles
CARD_BORDER_RADIUS = 12
CARD_PADDING = 20
DEFAULT_SPACING = 15

GLASS_CONTAINER_BG = ft.colors.SURFACE_VARIANT
ACCENT_COLOR = ft.colors.INDIGO
