"""Diet and nutritional planning view providing macronutrient calculations and recipe recommendations."""

from typing import Any, Dict, List
import flet as ft
import httpx

try:
    from frontend.components.navigation import get_adaptive_nav
    from frontend.components.zoom import create_zoom_controls, get_current_zoom
    from backend.calculations import calculate_diet_macronutrients, generate_recipes_by_meal_style
except ModuleNotFoundError:
    from components.navigation import get_adaptive_nav
    from components.zoom import create_zoom_controls, get_current_zoom
    from calculations import calculate_diet_macronutrients, generate_recipes_by_meal_style

API_BASE_URL = "http://localhost:8000"


def diet_view(page: ft.Page) -> ft.View:
    """Constructs the interactive diet blueprint, macro calculator, and meal recipe interface."""
    token = page.client_storage.get("token") or ""
    user_prof = page.client_storage.get("user_profile") if hasattr(page.client_storage, "get") else None
    init_weight = str(user_prof.get("weight_kg", 80.0)) if isinstance(user_prof, dict) and user_prof.get("weight_kg") else "80.0"
    init_height = str(user_prof.get("height_cm", 180.0)) if isinstance(user_prof, dict) and user_prof.get("height_cm") else "180.0"
    init_age = str(user_prof.get("age", 25)) if isinstance(user_prof, dict) and user_prof.get("age") else "25"
    init_bf = str(user_prof.get("body_fat_pct", "14.0")) if isinstance(user_prof, dict) and user_prof.get("body_fat_pct") is not None else "14.0"

    # Inputs for Macro & Diet Calculator
    weight_input = ft.TextField(label="Weight (kg)", value=init_weight, keyboard_type=ft.KeyboardType.NUMBER)
    height_input = ft.TextField(label="Height (cm)", value=init_height, keyboard_type=ft.KeyboardType.NUMBER)
    age_input = ft.TextField(label="Age (years)", value=init_age, keyboard_type=ft.KeyboardType.NUMBER)
    body_fat_input = ft.TextField(label="Body Fat % (Optional)", value=init_bf, keyboard_type=ft.KeyboardType.NUMBER)

    goal_dropdown = ft.Dropdown(
        label="Physiological Goal",
        value="maintenance",
        options=[
            ft.dropdown.Option("deficit", "Fat Loss / Caloric Deficit (-400 kcal)"),
            ft.dropdown.Option("maintenance", "Maintenance & Body Recomposition"),
            ft.dropdown.Option("surplus", "Muscle Hypertrophy Surplus (+300 kcal)"),
        ],
    )

    activity_dropdown = ft.Dropdown(
        label="Activity Level",
        value="1.55",
        options=[
            ft.dropdown.Option("1.2", "Sedentary (Desk Job, Minimal Exercise)"),
            ft.dropdown.Option("1.375", "Light Exercise (1-3 days/week)"),
            ft.dropdown.Option("1.55", "Moderate Training (3-5 days/week)"),
            ft.dropdown.Option("1.725", "Heavy Training (6-7 days/week)"),
            ft.dropdown.Option("1.9", "Very Heavy / Two-a-Days Athletic Load"),
        ],
    )

    meal_style_dropdown = ft.Dropdown(
        label="Meal Style & Frequency",
        value="3_meals",
        options=[
            ft.dropdown.Option("1_meal", "1 Meal a Day (OMAD Feast)"),
            ft.dropdown.Option("2_meals", "2 Meals a Day (Intermittent Fasting 16:8)"),
            ft.dropdown.Option("3_meals", "3 Meals a Day (Classic High-Protein Split)"),
        ],
    )

    snacks_switch = ft.Switch(label="Include High-Protein Snacks", value=True)
    drinks_switch = ft.Switch(label="Include Functional Hydration & Drinks", value=True)

    status_text = ft.Text(value="", size=12, color=ft.colors.PRIMARY)
    calc_button = ft.ElevatedButton("Calculate Macros & Generate Recipes", icon=ft.icons.RESTAURANT)

    # Macro Stat Cards
    cals_display = ft.Text("2,450 kcal", size=24, weight=ft.FontWeight.BOLD, color=ft.colors.INDIGO)
    protein_display = ft.Text("160 g", size=22, weight=ft.FontWeight.BOLD, color=ft.colors.BLUE_700)
    fat_display = ft.Text("68 g", size=22, weight=ft.FontWeight.BOLD, color=ft.colors.ORANGE_700)
    carbs_display = ft.Text("299 g", size=22, weight=ft.FontWeight.BOLD, color=ft.colors.GREEN_700)
    protocol_badge = ft.Text("Classic 3-Meal Athletic Blueprint", size=13, weight=ft.FontWeight.W_600, color=ft.colors.OUTLINE)

    meals_column = ft.Column(spacing=15)
    snacks_column = ft.Column(spacing=10)
    drinks_column = ft.Column(spacing=10)

    def render_plan(data: Dict[str, Any]) -> None:
        """Renders calculated plan and recipe cards into view."""
        cals = data.get("target_calories", 2450)
        prot = data.get("protein_g", 160)
        fat = data.get("fat_g", 68)
        carbs = data.get("carbs_g", 299)
        title = data.get("style_title", "Custom Nutrition Blueprint")

        cals_display.value = f"{cals:,} kcal"
        protein_display.value = f"{prot} g"
        fat_display.value = f"{fat} g"
        carbs_display.value = f"{carbs} g"
        protocol_badge.value = title

        if hasattr(page.client_storage, "set"):
            page.client_storage.set("active_diet_plan", data)

        # Build Meal Cards
        meals_column.controls.clear()
        for meal in data.get("meals", []):
            ingredients_list = ft.Column(
                [ft.Text(f"• {ing}", size=13) for ing in meal.get("ingredients", [])],
                spacing=4,
            )
            meal_card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Row([
                            ft.Icon(ft.icons.RESTAURANT_MENU, color=ft.colors.INDIGO, size=22),
                            ft.Text(meal.get("meal_name", "Meal"), size=16, weight=ft.FontWeight.BOLD),
                        ]),
                        ft.Container(
                            content=ft.Text(meal.get("timing_window", ""), size=11, color=ft.colors.OUTLINE),
                            padding=ft.padding.symmetric(horizontal=8, vertical=3),
                            border_radius=8,
                            bgcolor=ft.colors.SURFACE_VARIANT,
                        ),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(meal.get("recipe_title", ""), size=15, weight=ft.FontWeight.W_600, color=ft.colors.INDIGO),
                    ft.Row([
                        ft.Chip(label=ft.Text(f"{meal.get('calories', 0)} kcal"), bgcolor=ft.colors.INDIGO_50),
                        ft.Chip(label=ft.Text(f"Protein: {meal.get('protein_g', 0)}g"), bgcolor=ft.colors.BLUE_50),
                        ft.Chip(label=ft.Text(f"Fat: {meal.get('fat_g', 0)}g"), bgcolor=ft.colors.ORANGE_50),
                        ft.Chip(label=ft.Text(f"Carbs: {meal.get('carbs_g', 0)}g"), bgcolor=ft.colors.GREEN_50),
                    ], wrap=True, spacing=6),
                    ft.Divider(height=6, color=ft.colors.TRANSPARENT),
                    ft.Text("Ingredients:", size=13, weight=ft.FontWeight.BOLD),
                    ingredients_list,
                    ft.Divider(height=6, color=ft.colors.TRANSPARENT),
                    ft.Text("Preparation:", size=13, weight=ft.FontWeight.BOLD),
                    ft.Text(meal.get("instructions", ""), size=13, color=ft.colors.ON_SURFACE_VARIANT),
                ], spacing=10),
                padding=20,
                border_radius=12,
                bgcolor=ft.colors.SURFACE,
                border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
            )
            meals_column.controls.append(meal_card)

        # Build Snack Cards
        snacks_column.controls.clear()
        for snack in data.get("snacks", []):
            ing_list = ft.Column([ft.Text(f"• {i}", size=13) for i in snack.get("ingredients", [])], spacing=3)
            snack_card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Text(snack.get("name", "Power Snack"), size=15, weight=ft.FontWeight.BOLD, color=ft.colors.PRIMARY),
                        ft.Text(f"{snack.get('calories', 0)} kcal | {snack.get('protein_g', 0)}g Protein", size=12, color=ft.colors.OUTLINE),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ing_list,
                    ft.Text(f"Prep: {snack.get('instructions', '')}", size=12, italic=True),
                ], spacing=8),
                padding=14,
                border_radius=10,
                bgcolor=ft.colors.SURFACE,
                border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
            )
            snacks_column.controls.append(snack_card)

        # Build Drink Cards
        drinks_column.controls.clear()
        for drink in data.get("drinks", []):
            drink_card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.icons.LOCAL_DRINK, color=ft.colors.TEAL, size=20),
                        ft.Text(drink.get("name", "Functional Drink"), size=14, weight=ft.FontWeight.BOLD),
                        ft.Text(drink.get("timing", ""), size=11, color=ft.colors.OUTLINE),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Text(", ".join(drink.get("ingredients", [])), size=12),
                    ft.Text(drink.get("instructions", ""), size=12, italic=True, color=ft.colors.ON_SURFACE_VARIANT),
                ], spacing=6),
                padding=14,
                border_radius=10,
                bgcolor=ft.colors.SURFACE,
                border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
            )
            drinks_column.controls.append(drink_card)

    async def on_calculate_click(e: ft.ControlEvent) -> None:
        try:
            calc_button.disabled = True
            status_text.value = "Calculating metabolic blueprint & recipes..."
            page.update()

            w = float(weight_input.value or 80.0)
            h = float(height_input.value or 180.0)
            a = int(age_input.value or 25)
            bf = float(body_fat_input.value) if body_fat_input.value else None
            goal = goal_dropdown.value or "maintenance"
            act = float(activity_dropdown.value or 1.55)
            style = meal_style_dropdown.value or "3_meals"
            snack_flag = bool(snacks_switch.value)
            drink_flag = bool(drinks_switch.value)

            # Try backend endpoint first
            payload = {
                "weight_kg": w,
                "height_cm": h,
                "age": a,
                "gender": "male",
                "body_fat_pct": bf,
                "activity_multiplier": act,
                "goal": goal,
                "meal_style": style,
                "include_snacks": snack_flag,
                "include_drinks": drink_flag,
            }

            applied = False
            if token:
                try:
                    headers = {"Authorization": f"Bearer {token}"}
                    async with httpx.AsyncClient(timeout=8.0) as client:
                        res = await client.post(f"{API_BASE_URL}/api/diet/calculate", json=payload, headers=headers)
                        if res.status_code == 200:
                            render_plan(res.json())
                            status_text.value = "Diet & recipes calculated via sports science engine."
                            applied = True
                except Exception:
                    pass

            if not applied:
                # Local calculation fallback
                macros = calculate_diet_macronutrients(
                    weight_kg=w,
                    height_cm=h,
                    age=a,
                    gender="male",
                    body_fat_pct=bf,
                    activity_multiplier=act,
                    goal=goal,
                )
                plan = generate_recipes_by_meal_style(
                    target_calories=macros["target_calories"],
                    target_protein_g=macros["protein_g"],
                    target_fat_g=macros["fat_g"],
                    target_carbs_g=macros["carbs_g"],
                    meal_style=style,
                    include_snacks=snack_flag,
                    include_drinks=drink_flag,
                )
                combined = {**macros, **plan}
                render_plan(combined)
                status_text.value = "Diet calculated locally with verified physiological formulas."
        except Exception as err:
            status_text.value = f"Calculation error: {err}"
        finally:
            calc_button.disabled = False
            page.update()

    calc_button.on_click = on_calculate_click

    # Trigger initial plan calculation or load cached diet plan
    cached_diet = page.client_storage.get("active_diet_plan") if hasattr(page.client_storage, "get") else None
    if cached_diet and isinstance(cached_diet, dict):
        render_plan(cached_diet)
    else:
        w_val = float(weight_input.value or 80.0)
        h_val = float(height_input.value or 180.0)
        a_val = int(age_input.value or 25)
        bf_val = float(body_fat_input.value) if body_fat_input.value else None
        init_macros = calculate_diet_macronutrients(w_val, h_val, a_val, "male", bf_val, 1.55, "maintenance")
        init_plan = generate_recipes_by_meal_style(
            init_macros["target_calories"],
            init_macros["protein_g"],
            init_macros["fat_g"],
            init_macros["carbs_g"],
            "3_meals",
            True,
            True,
        )
        render_plan({**init_macros, **init_plan})

    # Top Macro Summary Row
    macro_cards_row = ft.ResponsiveRow([
        ft.Column(col={"xs": 12, "sm": 3}, controls=[
            ft.Container(
                content=ft.Column([
                    ft.Text("Target Daily Calories", size=12, color=ft.colors.OUTLINE),
                    cals_display,
                ]),
                padding=16,
                border_radius=12,
                bgcolor=ft.colors.SURFACE,
                border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
            )
        ]),
        ft.Column(col={"xs": 12, "sm": 3}, controls=[
            ft.Container(
                content=ft.Column([
                    ft.Text("Target Protein", size=12, color=ft.colors.OUTLINE),
                    protein_display,
                ]),
                padding=16,
                border_radius=12,
                bgcolor=ft.colors.SURFACE,
                border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
            )
        ]),
        ft.Column(col={"xs": 12, "sm": 3}, controls=[
            ft.Container(
                content=ft.Column([
                    ft.Text("Target Healthy Fats", size=12, color=ft.colors.OUTLINE),
                    fat_display,
                ]),
                padding=16,
                border_radius=12,
                bgcolor=ft.colors.SURFACE,
                border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
            )
        ]),
        ft.Column(col={"xs": 12, "sm": 3}, controls=[
            ft.Container(
                content=ft.Column([
                    ft.Text("Target Carbohydrates", size=12, color=ft.colors.OUTLINE),
                    carbs_display,
                ]),
                padding=16,
                border_radius=12,
                bgcolor=ft.colors.SURFACE,
                border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
            )
        ]),
    ])

    calculator_card = ft.Container(
        content=ft.Column([
            ft.Text("Macronutrient & Meal Style Calculator", style=ft.TextThemeStyle.TITLE_MEDIUM, weight=ft.FontWeight.BOLD),
            ft.ResponsiveRow([
                ft.Column(col={"xs": 12, "sm": 6}, controls=[weight_input]),
                ft.Column(col={"xs": 12, "sm": 6}, controls=[height_input]),
                ft.Column(col={"xs": 12, "sm": 6}, controls=[age_input]),
                ft.Column(col={"xs": 12, "sm": 6}, controls=[body_fat_input]),
                ft.Column(col={"xs": 12, "sm": 6}, controls=[goal_dropdown]),
                ft.Column(col={"xs": 12, "sm": 6}, controls=[activity_dropdown]),
                ft.Column(col={"xs": 12}, controls=[meal_style_dropdown]),
            ]),
            ft.Row([snacks_switch, drinks_switch], wrap=True, spacing=20),
            status_text,
            ft.Row([calc_button], alignment=ft.MainAxisAlignment.END),
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
                    ft.Icon(ft.icons.RESTAURANT, color=ft.colors.INDIGO, size=28),
                    ft.Text("Physiological Diet & Meal Blueprint", size=22, weight=ft.FontWeight.BOLD),
                ]),
                create_zoom_controls(page),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            macro_cards_row,
            ft.ResponsiveRow([
                ft.Column(col={"xs": 12, "md": 5}, controls=[calculator_card]),
                ft.Column(col={"xs": 12, "md": 7}, controls=[
                    ft.Row([
                        ft.Icon(ft.icons.AUTO_AWESOME, color=ft.colors.INDIGO, size=20),
                        protocol_badge,
                    ]),
                    meals_column,
                    ft.Divider(height=10, color=ft.colors.TRANSPARENT),
                    ft.Text("High-Protein Functional Snacks", size=16, weight=ft.FontWeight.BOLD),
                    snacks_column,
                    ft.Divider(height=10, color=ft.colors.TRANSPARENT),
                    ft.Text("Performance Hydration & Elixirs", size=16, weight=ft.FontWeight.BOLD),
                    drinks_column,
                ]),
            ]),
        ], spacing=20),
        padding=ft.padding.only(left=20, right=20, top=20, bottom=20 + extra_bottom),
        scale=ft.Scale(scale=current_scale, alignment=ft.alignment.top_center),
    )

    return ft.View(
        "/diet",
        scroll=ft.ScrollMode.AUTO,
        controls=[
            content_container,
            get_adaptive_nav(page, selected_index=1),
        ],
    )
