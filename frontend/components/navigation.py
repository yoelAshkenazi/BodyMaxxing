"""Adaptive navigation components for mobile (NavigationBar) and desktop (NavigationRail) layouts."""

import flet as ft


def get_adaptive_nav(page: ft.Page, selected_index: int) -> ft.Control:
    """Returns an adaptive bottom NavigationBar or desktop NavigationRail based on viewport dimensions."""
    destinations = [
        ft.NavigationBarDestination(icon=ft.icons.SHOW_CHART, label="Dashboard"),
        ft.NavigationBarDestination(icon=ft.icons.RESTAURANT, label="Diet"),
        ft.NavigationBarDestination(icon=ft.icons.SETTINGS, label="Settings"),
        ft.NavigationBarDestination(icon=ft.icons.LOGOUT, label="Sign Out"),
    ]

    async def on_nav_change(e: ft.ControlEvent) -> None:
        idx = e.control.selected_index
        if idx == 0:
            page.go("/dashboard")
        elif idx == 1:
            page.go("/diet")
        elif idx == 2:
            page.go("/settings")
        elif idx == 3:
            if hasattr(page.client_storage, "remove_async"):
                await page.client_storage.remove_async("token")
            else:
                page.client_storage.remove("token")
            page.go("/")

    return ft.NavigationBar(
        selected_index=selected_index,
        destinations=destinations,
        on_change=on_nav_change,
    )


def get_desktop_rail(page: ft.Page, selected_index: int) -> ft.NavigationRail:
    """Returns a persistent NavigationRail for wide desktop viewports."""
    async def on_rail_change(e: ft.ControlEvent) -> None:
        idx = e.control.selected_index
        if idx == 0:
            page.go("/dashboard")
        elif idx == 1:
            page.go("/diet")
        elif idx == 2:
            page.go("/settings")
        elif idx == 3:
            if hasattr(page.client_storage, "remove_async"):
                await page.client_storage.remove_async("token")
            else:
                page.client_storage.remove("token")
            page.go("/")

    return ft.NavigationRail(
        selected_index=selected_index,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=100,
        min_extended_width=200,
        leading=ft.Icon(ft.icons.FITNESS_CENTER, color=ft.colors.INDIGO, size=32),
        group_alignment=-0.9,
        destinations=[
            ft.NavigationRailDestination(
                icon=ft.icons.SHOW_CHART_OUTLINED,
                selected_icon=ft.icons.SHOW_CHART,
                label="Dashboard",
            ),
            ft.NavigationRailDestination(
                icon=ft.icons.RESTAURANT_OUTLINED,
                selected_icon=ft.icons.RESTAURANT,
                label="Diet",
            ),
            ft.NavigationRailDestination(
                icon=ft.icons.SETTINGS_OUTLINED,
                selected_icon=ft.icons.SETTINGS,
                label="Settings",
            ),
            ft.NavigationRailDestination(
                icon=ft.icons.LOGOUT_OUTLINED,
                selected_icon=ft.icons.LOGOUT,
                label="Sign Out",
            ),
        ],
        on_change=on_rail_change,
    )
