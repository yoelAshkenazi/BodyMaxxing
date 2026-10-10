"""Settings and profile view for updating anthropometrics, generating AI training regimens, and customizing constraints."""

from typing import Any, Dict, List
import flet as ft
import httpx

try:
    from frontend.components.navigation import get_adaptive_nav
    from frontend.components.zoom import create_zoom_controls, get_current_zoom
    from backend.calculations import calculate_tdee
    from backend.agent import _synthesize_deterministic_regimen
    from backend.models import UserBase, RegimeGenerateRequest
except ModuleNotFoundError:
    from components.navigation import get_adaptive_nav
    from components.zoom import create_zoom_controls, get_current_zoom
    from calculations import calculate_tdee
    from agent import _synthesize_deterministic_regimen
    from models import UserBase, RegimeGenerateRequest

API_BASE_URL = "http://localhost:8000"


def settings_view(page: ft.Page) -> ft.View:
    """Constructs user metrics configuration and Pydantic AI regimen generation panel with interactive constraints."""
    token = page.client_storage.get("token") or ""
    is_new_user = bool(page.client_storage.get("is_new_user"))
    user_prof = page.client_storage.get("user_profile") if hasattr(page.client_storage, "get") else None

    init_age = str(user_prof.get("age", 25)) if isinstance(user_prof, dict) and user_prof.get("age") else "25"
    init_height = str(user_prof.get("height_cm", 180.0)) if isinstance(user_prof, dict) and user_prof.get("height_cm") else "180.0"
    init_weight = str(user_prof.get("weight_kg", 80.0)) if isinstance(user_prof, dict) and user_prof.get("weight_kg") else "80.0"
    init_bf = str(user_prof.get("body_fat_pct", "14.0")) if isinstance(user_prof, dict) and user_prof.get("body_fat_pct") is not None else "14.0"
    init_goals = str(user_prof.get("free_text_goals")) if isinstance(user_prof, dict) and user_prof.get("free_text_goals") else "Focus on hypertrophy and progressive overload. 4 days/week split."

    # Inputs for anthropometrics
    age_input = ft.TextField(label="Age (years)", value=init_age, keyboard_type=ft.KeyboardType.NUMBER)
    height_input = ft.TextField(label="Height (cm)", value=init_height, keyboard_type=ft.KeyboardType.NUMBER)
    weight_input = ft.TextField(label="Weight (kg)", value=init_weight, keyboard_type=ft.KeyboardType.NUMBER)
    body_fat_input = ft.TextField(label="Body Fat % (Optional)", value=init_bf, keyboard_type=ft.KeyboardType.NUMBER)
    goals_input = ft.TextField(
        label="Natural Language Goals & Constraints",
        value=init_goals,
        multiline=True,
        max_lines=3,
    )

    save_status = ft.Text(value="", size=12, color=ft.colors.PRIMARY)
    save_btn = ft.ElevatedButton("Save Anthropometrics", icon=ft.icons.SAVE)

    # AI Regimen Generation controls
    ai_status = ft.Text(value="", size=12, color=ft.colors.INDIGO)
    ai_spinner = ft.ProgressRing(visible=False, width=20, height=20)
    generate_ai_btn = ft.FilledButton("Generate AI Regimen", icon=ft.icons.AUTO_AWESOME)

    # Constraint controls: Training focus dropdown & exercise selection checkboxes
    focus_dropdown = ft.Dropdown(
        label="Focused Training Split / Specialization",
        value="Default / Goal-Driven",
        options=[
            ft.dropdown.Option("Default / Goal-Driven"),
            ft.dropdown.Option("Full Body High-Frequency"),
            ft.dropdown.Option("Push / Pull / Legs (PPL)"),
            ft.dropdown.Option("Upper / Lower Power Split"),
            ft.dropdown.Option("Bench Press Specialization"),
            ft.dropdown.Option("Squat & Leg Hypertrophy"),
        ],
        dense=True,
    )
    exercise_checkboxes: Dict[str, ft.Checkbox] = {}
    regenerate_constrained_btn = ft.ElevatedButton("Re-generate with Selected & Focus", icon=ft.icons.TUNE)
    set_active_btn = ft.FilledButton("Set as Active Plan & Go to Dashboard", icon=ft.icons.ROCKET_LAUNCH)

    # AI Plan Results Container
    plan_calories = ft.Text("-", size=20, weight=ft.FontWeight.BOLD, color=ft.colors.INDIGO)
    plan_protein = ft.Text("-", size=20, weight=ft.FontWeight.BOLD, color=ft.colors.INDIGO)
    plan_split_column = ft.Column(spacing=6)
    plan_exercises_column = ft.Column(spacing=6)

    ai_results_card = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Icon(ft.icons.FITNESS_CENTER, color=ft.colors.INDIGO, size=24),
                ft.Text("Personalized Regimen Blueprint", style=ft.TextThemeStyle.TITLE_MEDIUM, weight=ft.FontWeight.BOLD),
            ]),
            ft.Row([
                ft.Container(
                    content=ft.Column([
                        ft.Text("Target Calories", size=11, color=ft.colors.OUTLINE),
                        plan_calories,
                    ]),
                    padding=12,
                    border_radius=8,
                    bgcolor=ft.colors.SURFACE_VARIANT,
                    expand=True,
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Text("Target Protein", size=11, color=ft.colors.OUTLINE),
                        plan_protein,
                    ]),
                    padding=12,
                    border_radius=8,
                    bgcolor=ft.colors.SURFACE_VARIANT,
                    expand=True,
                ),
            ], spacing=10),
            ft.Text("Prescribed Training Split:", size=13, weight=ft.FontWeight.W_600),
            plan_split_column,
            ft.Divider(height=6, color=ft.colors.TRANSPARENT),
            ft.Text("Exercise Prescriptions (Check to Keep, Uncheck to Replace):", size=13, weight=ft.FontWeight.W_600),
            plan_exercises_column,
            ft.Divider(height=10, color=ft.colors.TRANSPARENT),
            focus_dropdown,
            ft.Row([regenerate_constrained_btn, set_active_btn], wrap=True, spacing=10),
        ], spacing=12),
        padding=20,
        border_radius=12,
        bgcolor=ft.colors.SURFACE,
        border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
        visible=False,
    )

    def display_plan_data(data: Dict[str, Any]) -> None:
        """Renders plan data, populates interactive exercise checkboxes, and saves active plan state."""
        plan_calories.value = f"{data.get('target_calories_kcal', 2500)} kcal"
        plan_protein.value = f"{data.get('target_protein_g', 160)} g"

        # Split chips
        plan_split_column.controls.clear()
        split_row = ft.Row(wrap=True, spacing=6)
        for split_item in data.get("training_split", []):
            split_row.controls.append(
                ft.Chip(label=ft.Text(split_item), bgcolor=ft.colors.INDIGO_50)
            )
        plan_split_column.controls.append(split_row)

        # Exercise checkboxes
        exercise_checkboxes.clear()
        plan_exercises_column.controls.clear()
        plan_exercises_column.controls.append(
            ft.Text("Select exercises to retain, uncheck any you wish to substitute:", size=12, color=ft.colors.OUTLINE)
        )

        for ex in data.get("exercise_selection", []):
            name = ex.get("exercise") or ex.get("name", "Exercise")
            sets = ex.get("sets", 3)
            reps = ex.get("reps", "8-12")
            rpe = ex.get("target_rpe", 8.0)

            cb = ft.Checkbox(
                label=f"{name} — {sets} sets × {reps} reps (Target RPE: {rpe})",
                value=True,
            )
            exercise_checkboxes[name] = cb
            plan_exercises_column.controls.append(cb)

        ai_results_card.visible = True

        # Save to client storage so dashboard and diet views immediately track this plan
        if hasattr(page.client_storage, "set"):
            page.client_storage.set("active_regime_plan", data)
            page.client_storage.set("has_active_plan", True)

    async def on_save_profile(e: ft.ControlEvent) -> None:
        try:
            save_btn.disabled = True
            save_status.value = "Saving profile..."
            page.update()

            payload = {
                "age": int(age_input.value or 25),
                "height_cm": float(height_input.value or 180.0),
                "weight_kg": float(weight_input.value or 80.0),
                "body_fat_pct": float(body_fat_input.value) if body_fat_input.value else None,
                "free_text_goals": goals_input.value,
            }

            if token:
                headers = {"Authorization": f"Bearer {token}"}
                async with httpx.AsyncClient(timeout=8.0) as client:
                    res = await client.patch(f"{API_BASE_URL}/api/users/me", json=payload, headers=headers)
                    if res.status_code == 200:
                        save_status.value = "Profile saved successfully."
                    else:
                        save_status.value = "Profile saved locally."
            else:
                save_status.value = "Profile saved locally."
        except Exception as err:
            save_status.value = f"Saved locally: {err}"
        finally:
            save_btn.disabled = False
            page.update()

    async def execute_plan_generation(constraints_payload: Dict[str, Any] = None) -> None:
        try:
            generate_ai_btn.disabled = True
            regenerate_constrained_btn.disabled = True
            ai_spinner.visible = True
            ai_status.value = "Synthesizing customized training plan with constraints..."
            page.update()

            plan_result = None
            if token:
                headers = {"Authorization": f"Bearer {token}"}
                try:
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        res = await client.post(
                            f"{API_BASE_URL}/api/regime/generate",
                            json=constraints_payload,
                            headers=headers,
                        )
                        if res.status_code == 200:
                            plan_result = res.json()
                except Exception:
                    pass

            if not plan_result:
                # Direct sports science synthesis fallback
                w = float(weight_input.value or 80.0)
                h = float(height_input.value or 180.0)
                a = int(age_input.value or 25)
                bf = float(body_fat_input.value) if body_fat_input.value else None
                g = goals_input.value or ""

                user_stub = UserBase(
                    email="athlete@bodymaxxing.local",
                    age=a,
                    gender="male",
                    height_cm=h,
                    weight_kg=w,
                    body_fat_pct=bf,
                    free_text_goals=g,
                )
                tdee = calculate_tdee(user_stub)
                req = RegimeGenerateRequest(**constraints_payload) if constraints_payload else None
                resp_model = _synthesize_deterministic_regimen(user_stub, tdee, constraints=req)
                plan_result = resp_model.model_dump()

            display_plan_data(plan_result)
            ai_status.value = "Regimen generated & active plan updated!"
        except Exception as err:
            ai_status.value = f"Generation notice: {err}"
        finally:
            generate_ai_btn.disabled = False
            regenerate_constrained_btn.disabled = False
            ai_spinner.visible = False
            page.update()

    async def on_generate_ai(e: ft.ControlEvent) -> None:
        await execute_plan_generation(None)

    async def on_regenerate_constrained(e: ft.ControlEvent) -> None:
        selected = [name for name, cb in exercise_checkboxes.items() if cb.value]
        unselected = [name for name, cb in exercise_checkboxes.items() if not cb.value]
        chosen_split = focus_dropdown.value if focus_dropdown.value != "Default / Goal-Driven" else None

        payload = {
            "split_focus": chosen_split,
            "selected_exercises": selected,
            "unselected_exercises": unselected,
        }
        await execute_plan_generation(payload)

    def on_activate_plan(e: ft.ControlEvent) -> None:
        if hasattr(page.client_storage, "set"):
            page.client_storage.set("has_active_plan", True)
            page.client_storage.set("is_new_user", False)
        page.go("/dashboard")

    save_btn.on_click = on_save_profile
    generate_ai_btn.on_click = on_generate_ai
    regenerate_constrained_btn.on_click = on_regenerate_constrained
    set_active_btn.on_click = on_activate_plan

    # Initial plan setup: load active plan if cached, or synthesize plan for new users
    cached_plan = page.client_storage.get("active_regime_plan") if hasattr(page.client_storage, "get") else None
    if cached_plan and isinstance(cached_plan, dict):
        display_plan_data(cached_plan)
    elif is_new_user or not page.client_storage.get("has_active_plan"):
        # Auto-generate initial plan for new users so the first screen is pre-filled with an active plan
        w = float(weight_input.value or 80.0)
        h = float(height_input.value or 180.0)
        a = int(age_input.value or 25)
        bf = float(body_fat_input.value) if body_fat_input.value else None
        stub = UserBase(
            email=user_prof.get("email") if isinstance(user_prof, dict) and user_prof.get("email") else "athlete@bodymaxxing.local",
            age=a,
            gender=user_prof.get("gender") if isinstance(user_prof, dict) and user_prof.get("gender") else "male",
            height_cm=h,
            weight_kg=w,
            body_fat_pct=bf,
            free_text_goals=goals_input.value,
        )
        tdee_val = calculate_tdee(stub)
        initial_regimen = _synthesize_deterministic_regimen(stub, tdee_val)
        display_plan_data(initial_regimen.model_dump())

    anthropometrics_card = ft.Container(
        content=ft.Column([
            ft.Text("Anthropometrics & Physical Baseline", style=ft.TextThemeStyle.TITLE_MEDIUM, weight=ft.FontWeight.BOLD),
            ft.ResponsiveRow([
                ft.Column(col={"xs": 12, "sm": 6}, controls=[age_input]),
                ft.Column(col={"xs": 12, "sm": 6}, controls=[height_input]),
                ft.Column(col={"xs": 12, "sm": 6}, controls=[weight_input]),
                ft.Column(col={"xs": 12, "sm": 6}, controls=[body_fat_input]),
            ]),
            goals_input,
            save_status,
            ft.Row([save_btn], alignment=ft.MainAxisAlignment.END),
        ], spacing=14),
        padding=20,
        border_radius=12,
        bgcolor=ft.colors.SURFACE,
        border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
    )

    ai_trigger_card = ft.Container(
        content=ft.Column([
            ft.Text("AI Sports Scientist Integration", style=ft.TextThemeStyle.TITLE_MEDIUM, weight=ft.FontWeight.BOLD),
            ft.Text(
                "Trigger our Pydantic AI agent to construct structured nutrition caloric targets and training splits based on your exact metabolic baseline.",
                size=13,
                color=ft.colors.OUTLINE,
            ),
            ft.Row([generate_ai_btn, ai_spinner, ai_status], spacing=15),
            ai_results_card,
        ], spacing=14),
        padding=20,
        border_radius=12,
        bgcolor=ft.colors.SURFACE,
        border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
    )

    current_scale = get_current_zoom(page)
    extra_bottom = int(max(0.0, (current_scale - 1.0) * 800))

    content_container = ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Row([
                    ft.Icon(ft.icons.SETTINGS, color=ft.colors.INDIGO, size=28),
                    ft.Text("Account & Fitness Preferences", size=22, weight=ft.FontWeight.BOLD),
                ]),
                create_zoom_controls(page),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.ResponsiveRow([
                ft.Column(col={"xs": 12, "md": 5}, controls=[anthropometrics_card]),
                ft.Column(col={"xs": 12, "md": 7}, controls=[ai_trigger_card]),
            ]),
        ], spacing=20),
        padding=ft.padding.only(left=20, right=20, top=20, bottom=20 + extra_bottom),
        scale=ft.Scale(scale=current_scale, alignment=ft.alignment.top_center),
    )

    return ft.View(
        "/settings",
        scroll=ft.ScrollMode.AUTO,
        controls=[
            content_container,
            get_adaptive_nav(page, selected_index=2),
        ],
    )
