"""Primary tracking dashboard interface displaying strength charts, submaximal logging, regression trendlines, and active plan tracking."""

from typing import Any, Dict, List
import flet as ft
import httpx

try:
    from frontend.components.navigation import get_adaptive_nav
    from frontend.components.zoom import create_zoom_controls, get_current_zoom
except ModuleNotFoundError:
    from components.navigation import get_adaptive_nav
    from components.zoom import create_zoom_controls, get_current_zoom

API_BASE_URL = "http://localhost:8000"


def dashboard_view(page: ft.Page) -> ft.View:
    """Constructs the responsive tracking dashboard view with active regimen and diet progress tracking."""
    token = page.client_storage.get("token") or ""

    # Load active plans and tracking data from client storage
    active_plan = page.client_storage.get("active_regime_plan") if hasattr(page.client_storage, "get") else None
    active_diet = page.client_storage.get("active_diet_plan") if hasattr(page.client_storage, "get") else None
    completed_lifts = page.client_storage.get("completed_lifts") if hasattr(page.client_storage, "get") else {}
    if not isinstance(completed_lifts, dict):
        completed_lifts = {}
    daily_nutrition = page.client_storage.get("daily_nutrition_logged") if hasattr(page.client_storage, "get") else {}
    if not isinstance(daily_nutrition, dict):
        daily_nutrition = {"calories": 0, "protein": 0}

    # Extract prescribed exercises from active plan or default fallback
    if active_plan and isinstance(active_plan, dict) and active_plan.get("exercise_selection"):
        exercise_list: List[Dict[str, Any]] = active_plan.get("exercise_selection", [])
    else:
        exercise_list = [
            {"exercise": "Bench Press", "sets": 4, "reps": "6-8", "target_rpe": 8.5},
            {"exercise": "Back Squat", "sets": 3, "reps": "5-8", "target_rpe": 8.0},
            {"exercise": "Deadlift", "sets": 3, "reps": "5", "target_rpe": 8.5},
            {"exercise": "Overhead Press", "sets": 3, "reps": "6-8", "target_rpe": 8.5},
        ]

    exercise_names = [ex.get("exercise") or ex.get("name", "Lift") for ex in exercise_list]
    initial_exercise = exercise_names[0] if exercise_names else "Bench Press"

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

    chart_dropdown = ft.Dropdown(
        value=initial_exercise,
        options=[ft.dropdown.Option(name) for name in exercise_names],
        width=220,
        dense=True,
    )

    chart_container = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Text("1RM Strength Progression & Trendline", style=ft.TextThemeStyle.TITLE_MEDIUM, weight=ft.FontWeight.BOLD),
                chart_dropdown,
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
            ft.Container(content=trend_chart, height=280, padding=10),
        ]),
        padding=20,
        border_radius=12,
        bgcolor=ft.colors.SURFACE,
        border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
    )

    # Form inputs for logging submaximal lift
    exercise_input = ft.TextField(
        label="Exercise (e.g., Bench Press)",
        value=initial_exercise,
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

    async def on_chart_exercise_change(e: ft.ControlEvent) -> None:
        selected_ex = chart_dropdown.value or ""
        exercise_input.value = selected_ex
        if token:
            try:
                headers = {"Authorization": f"Bearer {token}"}
                async with httpx.AsyncClient(timeout=8.0) as client:
                    res = await client.get(
                        f"{API_BASE_URL}/api/tracking/forecast",
                        params={"exercise_name": selected_ex},
                        headers=headers,
                    )
                    if res.status_code == 200:
                        fc = res.json()
                        c1rm = fc.get("current_estimated_1rm") or 100.0
                        slope = fc.get("slope_kg_per_week") or 1.5
                        f4w = fc.get("forecast_4_weeks_1rm") or (c1rm + (slope * 4.0))
                        current_1rm_text.value = f"{c1rm:.1f} kg"
                        slope_text.value = f"+{slope:.1f} kg/wk" if slope >= 0 else f"{slope:.1f} kg/wk"
                        forecast_text.value = f"{f4w:.1f} kg"

                        history = fc.get("history", [])
                        if history:
                            chart_series.data_points = [
                                ft.LineChartDataPoint(idx + 1, pt.get("estimated_1rm", 100.0))
                                for idx, pt in enumerate(history)
                            ]
                            trend_chart.max_x = max(6, len(history) + 1)
                            y_vals = [pt.get("estimated_1rm", 100.0) for pt in history]
                            trend_chart.min_y = max(0, min(y_vals) - 15)
                            trend_chart.max_y = max(y_vals) + 15
            except Exception:
                pass
        page.update()

    chart_dropdown.on_change = on_chart_exercise_change

    # Prescriptions Tracker UI Components
    regimen_progress_text = ft.Text("", size=13, weight=ft.FontWeight.W_600)
    regimen_progress_bar = ft.ProgressBar(value=0.0, color=ft.colors.INDIGO, bgcolor=ft.colors.SURFACE_VARIANT, height=8)
    prescriptions_column = ft.Column(spacing=10)

    def refresh_regimen_tracker() -> None:
        prescriptions_column.controls.clear()
        total_ex = len(exercise_names)
        completed_count = sum(1 for name in exercise_names if name in completed_lifts)
        ratio = (completed_count / total_ex) if total_ex > 0 else 0.0

        regimen_progress_text.value = f"Regimen Completion: {completed_count} of {total_ex} Prescriptions Logged Today ({int(ratio * 100)}%)"
        regimen_progress_bar.value = ratio

        for ex in exercise_list:
            ex_name = ex.get("exercise") or ex.get("name", "Lift")
            sets = ex.get("sets", 3)
            reps = ex.get("reps", "8-12")
            rpe = ex.get("target_rpe", 8.0)

            is_done = ex_name in completed_lifts
            if is_done:
                info = completed_lifts[ex_name]
                status_chip = ft.Chip(
                    label=ft.Text(f"✓ Completed: {info.get('weight', 0)}kg × {info.get('reps', 0)} (1RM: {info.get('e1rm', 0)}kg)", size=11, color=ft.colors.GREEN_800),
                    bgcolor=ft.colors.GREEN_50,
                )
            else:
                status_chip = ft.Chip(
                    label=ft.Text(f"Prescribed: {sets} sets × {reps} @ RPE {rpe}", size=11, color=ft.colors.INDIGO_900),
                    bgcolor=ft.colors.INDIGO_50,
                )

            def make_select_handler(name: str):
                def select_exercise(e: ft.ControlEvent) -> None:
                    exercise_input.value = name
                    chart_dropdown.value = name
                    page.update()
                return select_exercise

            row = ft.Container(
                content=ft.Row([
                    ft.Row([
                        ft.Icon(ft.icons.CHECK_CIRCLE if is_done else ft.icons.RADIO_BUTTON_UNCHECKED, color=ft.colors.GREEN if is_done else ft.colors.OUTLINE, size=20),
                        ft.Text(ex_name, size=14, weight=ft.FontWeight.BOLD),
                    ], spacing=8),
                    ft.Row([
                        status_chip,
                        ft.TextButton("Select", icon=ft.icons.PLAY_ARROW, on_click=make_select_handler(ex_name)),
                    ], spacing=6),
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
                padding=10,
                border_radius=8,
                bgcolor=ft.colors.SURFACE_VARIANT if not is_done else ft.colors.with_opacity(0.1, ft.colors.GREEN),
            )
            prescriptions_column.controls.append(row)

    refresh_regimen_tracker()

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

            e1rm_val = 0.0
            headers = {"Authorization": f"Bearer {token}"}
            saved_ok = False
            if token:
                try:
                    async with httpx.AsyncClient(timeout=8.0) as client:
                        res = await client.post(
                            f"{API_BASE_URL}/api/tracking/lifts",
                            json={"exercise_name": ex, "weight_lifted": w, "repetitions": r},
                            headers=headers,
                        )
                    if res.status_code == 201:
                        saved = res.json()
                        e1rm_val = saved.get("estimated_1rm", 0.0)
                        current_1rm_text.value = f"{e1rm_val:.1f} kg"
                        form_status.value = f"Success! Estimated 1RM: {e1rm_val:.1f} kg"
                        saved_ok = True
                except Exception:
                    pass

            if not saved_ok:
                epley = w * (1.0 + (r / 30.0))
                brzycki = w / (1.0278 - (0.0278 * r))
                e1rm_val = round((epley + brzycki) / 2.0, 2)
                current_1rm_text.value = f"{e1rm_val:.1f} kg"
                form_status.value = f"Saved locally. Estimated 1RM: {e1rm_val:.1f} kg"

            # Add data point to strength trendline chart
            new_x = len(chart_series.data_points) + 1
            chart_series.data_points.append(ft.LineChartDataPoint(new_x, e1rm_val))
            trend_chart.max_x = max(trend_chart.max_x, new_x + 1)
            trend_chart.max_y = max(trend_chart.max_y, e1rm_val + 10)

            # Record in active regimen completed lifts & persist
            completed_lifts[ex] = {"weight": w, "reps": r, "e1rm": round(e1rm_val, 1)}
            if hasattr(page.client_storage, "set"):
                page.client_storage.set("completed_lifts", completed_lifts)
            refresh_regimen_tracker()

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

    # Active Nutrition Tracking Section
    target_cals = int((active_diet.get("target_calories") if active_diet else None) or (active_plan.get("target_calories_kcal") if active_plan else None) or 2450)
    target_prot = int((active_diet.get("protein_g") if active_diet else None) or (active_plan.get("target_protein_g") if active_plan else None) or 160)

    logged_cals = int(daily_nutrition.get("calories", 0))
    logged_prot = int(daily_nutrition.get("protein", 0))

    cal_stat_text = ft.Text(f"{logged_cals:,} / {target_cals:,} kcal", size=15, weight=ft.FontWeight.BOLD, color=ft.colors.INDIGO)
    cal_progress_bar = ft.ProgressBar(value=min(1.0, logged_cals / target_cals if target_cals > 0 else 0.0), color=ft.colors.INDIGO, bgcolor=ft.colors.SURFACE_VARIANT, height=8)

    prot_stat_text = ft.Text(f"{logged_prot} / {target_prot} g", size=15, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_700)
    prot_progress_bar = ft.ProgressBar(value=min(1.0, logged_prot / target_prot if target_prot > 0 else 0.0), color=ft.colors.BLUE_700, bgcolor=ft.colors.SURFACE_VARIANT, height=8)

    custom_cal_input = ft.TextField(label="+ Calories (kcal)", value="250", keyboard_type=ft.KeyboardType.NUMBER, dense=True, width=130)
    custom_prot_input = ft.TextField(label="+ Protein (g)", value="20", keyboard_type=ft.KeyboardType.NUMBER, dense=True, width=130)

    def update_nutrition_state() -> None:
        nonlocal logged_cals, logged_prot
        cal_stat_text.value = f"{logged_cals:,} / {target_cals:,} kcal ({int(min(100.0, (logged_cals / target_cals) * 100)) if target_cals else 0}%)"
        cal_progress_bar.value = min(1.0, logged_cals / target_cals if target_cals > 0 else 0.0)
        prot_stat_text.value = f"{logged_prot} / {target_prot} g ({int(min(100.0, (logged_prot / target_prot) * 100)) if target_prot else 0}%)"
        prot_progress_bar.value = min(1.0, logged_prot / target_prot if target_prot > 0 else 0.0)

        if hasattr(page.client_storage, "set"):
            page.client_storage.set("daily_nutrition_logged", {"calories": logged_cals, "protein": logged_prot})
        page.update()

    def add_quick_nutrition(added_cals: int, added_prot: int):
        def handler(e: ft.ControlEvent) -> None:
            nonlocal logged_cals, logged_prot
            logged_cals += added_cals
            logged_prot += added_prot
            update_nutrition_state()
        return handler

    def on_custom_intake(e: ft.ControlEvent) -> None:
        nonlocal logged_cals, logged_prot
        try:
            c = int(custom_cal_input.value or 0)
            p = int(custom_prot_input.value or 0)
            logged_cals += max(0, c)
            logged_prot += max(0, p)
            update_nutrition_state()
        except Exception:
            pass

    def on_reset_nutrition(e: ft.ControlEvent) -> None:
        nonlocal logged_cals, logged_prot
        logged_cals = 0
        logged_prot = 0
        update_nutrition_state()

    quick_shake_btn = ft.ElevatedButton("+30g Whey Shake", icon=ft.icons.LOCAL_DRINK, on_click=add_quick_nutrition(140, 30))
    quick_meal500_btn = ft.ElevatedButton("+500 kcal Meal", icon=ft.icons.RESTAURANT, on_click=add_quick_nutrition(500, 35))
    quick_meal750_btn = ft.ElevatedButton("+750 kcal Heavy Meal", icon=ft.icons.LUNCH_DINING, on_click=add_quick_nutrition(750, 50))
    add_custom_btn = ft.FilledButton("Log Intake", icon=ft.icons.ADD, on_click=on_custom_intake)
    reset_nutrition_btn = ft.TextButton("Reset Today's Log", icon=ft.icons.REPLAY, on_click=on_reset_nutrition)

    diet_tracker_card = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Row([
                    ft.Icon(ft.icons.RESTAURANT_MENU, color=ft.colors.INDIGO, size=24),
                    ft.Text("Active Nutrition & Macro Progress", style=ft.TextThemeStyle.TITLE_MEDIUM, weight=ft.FontWeight.BOLD),
                ]),
                reset_nutrition_btn,
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Text("Daily Caloric Intake vs Target:", size=12, color=ft.colors.OUTLINE),
            ft.Row([cal_stat_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            cal_progress_bar,
            ft.Divider(height=6, color=ft.colors.TRANSPARENT),
            ft.Text("Daily Protein Intake vs Target:", size=12, color=ft.colors.OUTLINE),
            ft.Row([prot_stat_text], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            prot_progress_bar,
            ft.Divider(height=6, color=ft.colors.TRANSPARENT),
            ft.Text("Quick Macro Increments:", size=12, weight=ft.FontWeight.W_600),
            ft.Row([quick_shake_btn, quick_meal500_btn, quick_meal750_btn], wrap=True, spacing=8),
            ft.Divider(height=6, color=ft.colors.TRANSPARENT),
            ft.Row([custom_cal_input, custom_prot_input, add_custom_btn], wrap=True, spacing=8, alignment=ft.MainAxisAlignment.START),
        ], spacing=10),
        padding=20,
        border_radius=12,
        bgcolor=ft.colors.SURFACE,
        border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
    )

    regimen_tracker_card = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Row([
                    ft.Icon(ft.icons.CHECKLIST, color=ft.colors.INDIGO, size=24),
                    ft.Text("Active Plan Prescriptions & Workout Progress", style=ft.TextThemeStyle.TITLE_MEDIUM, weight=ft.FontWeight.BOLD),
                ]),
                ft.FilledTonalButton("Plan Settings", icon=ft.icons.SETTINGS, on_click=lambda e: page.go("/settings")),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
            regimen_progress_text,
            regimen_progress_bar,
            ft.Divider(height=6, color=ft.colors.TRANSPARENT),
            prescriptions_column,
        ], spacing=12),
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

    # Active plan split banner chips
    split_chips_row = ft.Row(wrap=True, spacing=6)
    if active_plan and isinstance(active_plan, dict) and active_plan.get("training_split"):
        for sp in active_plan.get("training_split", [])[:4]:
            split_chips_row.controls.append(ft.Chip(label=ft.Text(sp, size=11), bgcolor=ft.colors.INDIGO_50))
    else:
        split_chips_row.controls.append(ft.Chip(label=ft.Text("Full Body Power & Hypertrophy Baseline", size=11), bgcolor=ft.colors.INDIGO_50))

    active_banner = ft.Container(
        content=ft.Row([
            ft.Row([
                ft.Icon(ft.icons.AUTO_AWESOME, color=ft.colors.INDIGO, size=20),
                ft.Text("Current Active Regimen & Nutritional Split:", size=13, weight=ft.FontWeight.BOLD),
            ]),
            split_chips_row,
        ], wrap=True, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        padding=12,
        border_radius=10,
        bgcolor=ft.colors.SURFACE,
        border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
    )

    current_scale = get_current_zoom(page)
    extra_bottom = int(max(0.0, (current_scale - 1.0) * 800))

    content_container = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Row([
                    ft.Icon(ft.icons.FITNESS_CENTER, color=ft.colors.INDIGO, size=28),
                    ft.Text("Strength Progression & Regimen Dashboard", size=22, weight=ft.FontWeight.BOLD),
                ]),
                create_zoom_controls(page),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            active_banner,
            metric_cards,
            ft.ResponsiveRow([
                # Left column: Active Regimen Prescriptions + Trendline Chart
                ft.Column(col={"xs": 12, "lg": 7}, controls=[
                    regimen_tracker_card,
                    chart_container,
                ]),
                # Right column: Submaximal Logging Form + Diet Macro Progress
                ft.Column(col={"xs": 12, "lg": 5}, controls=[
                    logging_form,
                    diet_tracker_card,
                ]),
            ]),
        ], spacing=20),
        padding=ft.padding.only(left=20, right=20, top=20, bottom=20 + extra_bottom),
        scale=ft.Scale(scale=current_scale, alignment=ft.alignment.top_center),
    )

    return ft.View(
        "/dashboard",
        scroll=ft.ScrollMode.AUTO,
        controls=[
            content_container,
            get_adaptive_nav(page, selected_index=0),
        ],
    )

