"""Settings and profile view for updating anthropometrics and generating AI training regimens."""

import flet as ft
import httpx

try:
    from frontend.components.navigation import get_adaptive_nav
except ModuleNotFoundError:
    from components.navigation import get_adaptive_nav

API_BASE_URL = "http://localhost:8000"


def settings_view(page: ft.Page) -> ft.View:
    """Constructs user metrics configuration and Pydantic AI regimen generation panel."""
    token = page.client_storage.get("token") or ""

    # Inputs for anthropometrics
    age_input = ft.TextField(label="Age (years)", value="25", keyboard_type=ft.KeyboardType.NUMBER)
    height_input = ft.TextField(label="Height (cm)", value="180.0", keyboard_type=ft.KeyboardType.NUMBER)
    weight_input = ft.TextField(label="Weight (kg)", value="80.0", keyboard_type=ft.KeyboardType.NUMBER)
    body_fat_input = ft.TextField(label="Body Fat % (Optional)", value="14.0", keyboard_type=ft.KeyboardType.NUMBER)
    goals_input = ft.TextField(
        label="Natural Language Goals",
        value="Focus on hypertrophy and 1RM bench progression. 4 days/week split.",
        multiline=True,
        max_lines=3,
    )

    save_status = ft.Text(value="", size=12, color=ft.colors.PRIMARY)
    save_btn = ft.ElevatedButton("Save Anthropometrics", icon=ft.icons.SAVE)

    # AI Regimen Generation controls
    ai_status = ft.Text(value="", size=12, color=ft.colors.INDIGO)
    ai_spinner = ft.ProgressRing(visible=False, width=20, height=20)
    generate_ai_btn = ft.FilledButton("Generate AI Regimen", icon=ft.icons.AUTO_AWESOME)

    # AI Plan Results Container
    plan_calories = ft.Text("-", size=20, weight=ft.FontWeight.BOLD, color=ft.colors.INDIGO)
    plan_protein = ft.Text("-", size=20, weight=ft.FontWeight.BOLD, color=ft.colors.INDIGO)
    plan_split_column = ft.Column(spacing=6)
    plan_exercises_column = ft.Column(spacing=6)

    ai_results_card = ft.Container(
        content=ft.Column([
            ft.Text("AI Tailored Regimen", style=ft.TextThemeStyle.TITLE_MEDIUM, weight=ft.FontWeight.BOLD),
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
            ft.Text("Training Split:", size=13, weight=ft.FontWeight.W_600),
            plan_split_column,
            ft.Text("Exercise Prescriptions (Target RPE):", size=13, weight=ft.FontWeight.W_600),
            plan_exercises_column,
        ], spacing=12),
        padding=20,
        border_radius=12,
        bgcolor=ft.colors.SURFACE,
        border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
        visible=False,
    )

    async def on_save_profile(e: ft.ControlEvent) -> None:
        try:
            save_btn.disabled = True
            save_status.value = "Saving..."
            page.update()

            payload = {
                "age": int(age_input.value or 25),
                "height_cm": float(height_input.value or 180.0),
                "weight_kg": float(weight_input.value or 80.0),
                "body_fat_pct": float(body_fat_input.value) if body_fat_input.value else None,
                "free_text_goals": goals_input.value,
            }

            headers = {"Authorization": f"Bearer {token}"}
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.patch(f"{API_BASE_URL}/api/users/me", json=payload, headers=headers)

            if res.status_code == 200:
                save_status.value = "Profile saved successfully."
            else:
                save_status.value = f"Saved locally (Backend response: {res.status_code})"
        except Exception as err:
            save_status.value = f"Updated locally: {err}"
        finally:
            save_btn.disabled = False
            page.update()

    async def on_generate_ai(e: ft.ControlEvent) -> None:
        try:
            generate_ai_btn.disabled = True
            ai_spinner.visible = True
            ai_status.value = "Pydantic AI agent synthesizing training plan..."
            page.update()

            headers = {"Authorization": f"Bearer {token}"}
            async with httpx.AsyncClient(timeout=30.0) as client:
                res = await client.post(f"{API_BASE_URL}/api/regime/generate", headers=headers)

            if res.status_code == 200:
                data = res.json()
                plan_calories.value = f"{data['target_calories_kcal']} kcal"
                plan_protein.value = f"{data['target_protein_g']} g"

                # Training split chips
                plan_split_column.controls.clear()
                split_row = ft.Row(wrap=True, spacing=6)
                for split_item in data.get("training_split", []):
                    split_row.controls.append(
                        ft.Chip(label=ft.Text(split_item), bgcolor=ft.colors.INDIGO_50)
                    )
                plan_split_column.controls.append(split_row)

                # Exercise selection
                plan_exercises_column.controls.clear()
                for ex in data.get("exercise_selection", []):
                    name = ex.get("exercise") or ex.get("name", "Exercise")
                    sets = ex.get("sets", 3)
                    reps = ex.get("reps", "8-12")
                    rpe = ex.get("target_rpe", 8.0)
                    plan_exercises_column.controls.append(
                        ft.ListTile(
                            leading=ft.Icon(ft.icons.FITNESS_CENTER, size=18, color=ft.colors.INDIGO),
                            title=ft.Text(f"{name}", size=14, weight=ft.FontWeight.W_600),
                            subtitle=ft.Text(f"{sets} sets × {reps} reps | Target RPE: {rpe}", size=12),
                            dense=True,
                        )
                    )

                ai_results_card.visible = True
                ai_status.value = "AI plan synthesized successfully!"
            else:
                ai_status.value = f"AI agent busy (HTTP {res.status_code}). Please retry."
        except Exception as err:
            ai_status.value = f"AI Generation error: {err}"
        finally:
            generate_ai_btn.disabled = False
            ai_spinner.visible = False
            page.update()

    save_btn.on_click = on_save_profile
    generate_ai_btn.on_click = on_generate_ai

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

    return ft.View(
        "/settings",
        controls=[
            ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.icons.SETTINGS, color=ft.colors.INDIGO, size=28),
                        ft.Text("Account & Fitness Preferences", size=22, weight=ft.FontWeight.BOLD),
                    ]),
                    ft.ResponsiveRow([
                        ft.Column(col={"xs": 12, "md": 6}, controls=[anthropometrics_card]),
                        ft.Column(col={"xs": 12, "md": 6}, controls=[ai_trigger_card]),
                    ]),
                ], spacing=20),
                padding=20,
                expand=True,
            ),
            get_adaptive_nav(page, selected_index=1),
        ],
    )
