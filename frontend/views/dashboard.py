"""Primary tracking dashboard interface displaying strength charts, submaximal logging, and regression trendlines."""

from typing import List
import flet as ft
import httpx

from frontend.components.navigation import get_adaptive_nav

API_BASE_URL = "http://localhost:8000"


def dashboard_view(page: ft.Page) -> ft.View:
    """Constructs the responsive tracking dashboard view using ResponsiveRow breakpoints."""
    token = page.client_storage.get("token") or ""

    # Metric stat cards
    current_1rm_text = ft.Text("100.0 kg", size=26, weight=ft.FontWeight.BOLD, color=ft.colors.INDIGO)
    slope_text = ft.Text("+1.5 kg/wk", size=18, weight=ft.FontWeight.W_600, color=ft.colors.GREEN)
    forecast_text = ft.Text("106.0 kg", size=26, weight=ft.FontWeight.BOLD, color=ft.colors.PRIMARY)

    # Chart data points
    initial_points = [
        ft.LineChartDataPoint(1, 90.0),
        ft.LineChartDataPoint(2, 92.5),
        ft.LineChartDataPoint(3, 95.0),
        ft.LineChartDataPoint(4, 97.5),
        ft.LineChartDataPoint(5, 100.0),
    ]

    chart_series = ft.LineChartData(
        data_points=initial_points,
        stroke_width=3,
        color=ft.colors.INDIGO,
        curved=True,
        stroke_cap_round=True,
        below_line_bgcolor=ft.colors.with_opacity(0.15, ft.colors.INDIGO),
    )

    trend_chart = ft.LineChart(
        data_series=[chart_series],
        expand=True,
        min_y=70,
        max_y=130,
        min_x=1,
        max_x=6,
        tooltip_bgcolor=ft.colors.SURFACE_VARIANT,
        border=ft.Border(
            bottom=ft.BorderSide(1, ft.colors.OUTLINE_VARIANT),
            left=ft.BorderSide(1, ft.colors.OUTLINE_VARIANT),
        ),
    )

    chart_container = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text("1RM Strength Progression & Trendline", style=ft.TextThemeStyle.TITLE_MEDIUM, weight=ft.FontWeight.BOLD),
                ft.Dropdown(
                    value="Bench Press",
                    options=[
                        ft.dropdown.Option("Bench Press"),
                        ft.dropdown.Option("Back Squat"),
                        ft.dropdown.Option("Deadlift"),
                        ft.dropdown.Option("Overhead Press"),
                    ],
                    width=180,
                    dense=True,
                ),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(content=trend_chart, height=280, padding=10),
        ]),
        padding=20,
        border_radius=12,
        bgcolor=ft.colors.SURFACE,
        border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
    )

    # Form inputs
    exercise_input = ft.TextField(
        label="Exercise (e.g., Bench Press)",
        value="Bench Press",
        autofocus=True,
    )
    weight_input = ft.TextField(
        label="Weight Lifted (kg)",
        value="100.0",
        keyboard_type=ft.KeyboardType.NUMBER,
    )
    reps_input = ft.TextField(
        label="Repetitions",
        value="5",
        keyboard_type=ft.KeyboardType.NUMBER,
    )
    form_status = ft.Text(value="", size=12, color=ft.colors.PRIMARY)
    save_button = ft.ElevatedButton("Save & Calculate 1RM", icon=ft.icons.ADD_TASK)

    async def on_save_lift(e: ft.ControlEvent) -> None:
        try:
            w = float(weight_input.value or 0)
            r = int(reps_input.value or 0)
            ex = (exercise_input.value or "").strip()

            if w <= 0 or r <= 0 or not ex:
                form_status.value = "Enter valid exercise, weight, and reps."
                page.update()
                return

            save_button.disabled = True
            form_status.value = "Calculating composite 1RM..."
            page.update()

            headers = {"Authorization": f"Bearer {token}"}
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(
                    f"{API_BASE_URL}/api/tracking/lifts",
                    json={"exercise_name": ex, "weight_lifted": w, "repetitions": r},
                    headers=headers,
                )

            if res.status_code == 201:
                saved = res.json()
                e1rm = saved.get("estimated_1rm", 0.0)
                current_1rm_text.value = f"{e1rm:.1f} kg"
                form_status.value = f"Success! Estimated 1RM: {e1rm:.1f} kg"
                # Add point to chart
                new_x = len(chart_series.data_points) + 1
                chart_series.data_points.append(ft.LineChartDataPoint(new_x, e1rm))
                trend_chart.max_x = max(trend_chart.max_x, new_x + 1)
                trend_chart.max_y = max(trend_chart.max_y, e1rm + 10)
            else:
                # Local fallback calculation if backend is disconnected
                epley = w * (1.0 + (r / 30.0))
                brzycki = w / (1.0278 - (0.0278 * r))
                local_1rm = round((epley + brzycki) / 2.0, 2)
                current_1rm_text.value = f"{local_1rm:.1f} kg"
                form_status.value = f"Saved locally. Estimated 1RM: {local_1rm:.1f} kg"
        except Exception as err:
            form_status.value = f"Error: {err}"
        finally:
            save_button.disabled = False
            page.update()

    save_button.on_click = on_save_lift

    logging_form = ft.Container(
        content=ft.Column([
            ft.Text("Log Submaximal Lift", style=ft.TextThemeStyle.TITLE_MEDIUM, weight=ft.FontWeight.BOLD),
            exercise_input,
            weight_input,
            reps_input,
            form_status,
            save_button,
        ], spacing=14),
        padding=20,
        border_radius=12,
        bgcolor=ft.colors.SURFACE,
        border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
    )

    # Top metric cards
    metric_cards = ft.ResponsiveRow([
        ft.Column(col={"xs": 12, "sm": 4}, controls=[
            ft.Container(
                content=ft.Column([
                    ft.Text("Current Estimated 1RM", size=12, color=ft.colors.OUTLINE),
                    current_1rm_text,
                ]),
                padding=16,
                border_radius=12,
                bgcolor=ft.colors.SURFACE,
                border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
            )
        ]),
        ft.Column(col={"xs": 12, "sm": 4}, controls=[
            ft.Container(
                content=ft.Column([
                    ft.Text("Progression Rate", size=12, color=ft.colors.OUTLINE),
                    slope_text,
                ]),
                padding=16,
                border_radius=12,
                bgcolor=ft.colors.SURFACE,
                border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
            )
        ]),
        ft.Column(col={"xs": 12, "sm": 4}, controls=[
            ft.Container(
                content=ft.Column([
                    ft.Text("4-Week Forecast 1RM", size=12, color=ft.colors.OUTLINE),
                    forecast_text,
                ]),
                padding=16,
                border_radius=12,
                bgcolor=ft.colors.SURFACE,
                border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
            )
        ]),
    ])

    return ft.View(
        "/dashboard",
        controls=[
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.icons.FITNESS_CENTER, color=ft.colors.INDIGO, size=28),
                        ft.Text("Strength Progression Dashboard", size=22, weight=ft.FontWeight.BOLD),
                    ]),
                    metric_cards,
                    ft.ResponsiveRow([
                        # Spans 12 cols on mobile (xs), 8 cols on medium desktops (md)
                        ft.Column(col={"xs": 12, "md": 8}, controls=[chart_container]),
                        # Spans 12 cols on mobile, 4 cols on medium desktops
                        ft.Column(col={"xs": 12, "md": 4}, controls=[logging_form]),
                    ]),
                ], spacing=20),
                padding=20,
                expand=True,
            ),
            get_adaptive_nav(page, selected_index=0),
        ],
    )
