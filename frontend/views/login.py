"""Authentication view providing login and user registration interfaces."""

import flet as ft
import httpx

API_BASE_URL = "http://localhost:8000"


def login_view(page: ft.Page) -> ft.View:
    """Constructs the responsive login and registration interface."""
    is_register_mode = False

    # Input controls
    email_field = ft.TextField(
        label="Email Address",
        prefix_icon=ft.icons.EMAIL_OUTLINED,
        autofocus=True,
        keyboard_type=ft.KeyboardType.EMAIL,
    )
    password_field = ft.TextField(
        label="Password",
        prefix_icon=ft.icons.LOCK_OUTLINE,
        password=True,
        can_reveal_password=True,
    )

    # Registration-only fields
    age_field = ft.TextField(label="Age", value="25", keyboard_type=ft.KeyboardType.NUMBER, visible=False)
    height_field = ft.TextField(label="Height (cm)", value="180.0", keyboard_type=ft.KeyboardType.NUMBER, visible=False)
    weight_field = ft.TextField(label="Weight (kg)", value="80.0", keyboard_type=ft.KeyboardType.NUMBER, visible=False)
    goals_field = ft.TextField(
        label="Fitness Goals (Optional)",
        multiline=True,
        max_lines=3,
        visible=False,
    )

    status_message = ft.Text(value="", color=ft.colors.ERROR, size=13)
    loading_indicator = ft.ProgressRing(visible=False, width=20, height=20)

    title_text = ft.Text("BodyMaxxing", size=28, weight=ft.FontWeight.BOLD, color=ft.colors.INDIGO)
    subtitle_text = ft.Text("Sign in to track submaximal lifts & AI regimens", size=14, color=ft.colors.OUTLINE)
    action_button = ft.ElevatedButton("Sign In", icon=ft.icons.LOGIN)
    toggle_text_btn = ft.TextButton("Don't have an account? Sign Up")

    def toggle_mode(e: ft.ControlEvent) -> None:
        nonlocal is_register_mode
        is_register_mode = not is_register_mode
        age_field.visible = is_register_mode
        height_field.visible = is_register_mode
        weight_field.visible = is_register_mode
        goals_field.visible = is_register_mode
        status_message.value = ""

        if is_register_mode:
            title_text.value = "Create Account"
            subtitle_text.value = "Start your progressive overload journey"
            action_button.text = "Register Account"
            toggle_text_btn.text = "Already have an account? Sign In"
        else:
            title_text.value = "BodyMaxxing"
            subtitle_text.value = "Sign in to track submaximal lifts & AI regimens"
            action_button.text = "Sign In"
            toggle_text_btn.text = "Don't have an account? Sign Up"

        page.update()

    async def submit_auth(e: ft.ControlEvent) -> None:
        email = email_field.value.strip() if email_field.value else ""
        password = password_field.value.strip() if password_field.value else ""

        if not email or not password:
            status_message.value = "Please enter both email and password."
            page.update()
            return

        loading_indicator.visible = True
        status_message.value = ""
        action_button.disabled = True
        page.update()

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                if is_register_mode:
                    payload = {
                        "email": email,
                        "password": password,
                        "age": int(age_field.value or 25),
                        "gender": "unspecified",
                        "height_cm": float(height_field.value or 180.0),
                        "weight_kg": float(weight_field.value or 80.0),
                        "free_text_goals": goals_field.value or "Strength and hypertrophy",
                    }
                    res = await client.post(f"{API_BASE_URL}/api/auth/register", json=payload)
                else:
                    payload = {"email": email, "password": password}
                    res = await client.post(f"{API_BASE_URL}/api/auth/login", json=payload)

            if res.status_code in (200, 201):
                data = res.json()
                token = data.get("access_token")
                if token:
                    page.client_storage.set("token", token)
                    page.go("/dashboard")
                    return
            else:
                detail = res.json().get("detail", "Authentication failed.")
                status_message.value = str(detail)
        except Exception as err:
            status_message.value = f"Connection error: {err}"
        finally:
            loading_indicator.visible = False
            action_button.disabled = False
            page.update()

    action_button.on_click = submit_auth
    toggle_text_btn.on_click = toggle_mode

    form_card = ft.Container(
        content=ft.Column(
            controls=[
                ft.Row([ft.Icon(ft.icons.FITNESS_CENTER, color=ft.colors.INDIGO, size=36), title_text], alignment=ft.MainAxisAlignment.CENTER),
                subtitle_text,
                ft.Divider(height=10, color=ft.colors.TRANSPARENT),
                email_field,
                password_field,
                age_field,
                height_field,
                weight_field,
                goals_field,
                status_message,
                ft.Row([action_button, loading_indicator], alignment=ft.MainAxisAlignment.CENTER, spacing=15),
                toggle_text_btn,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
        ),
        padding=30,
        border_radius=16,
        bgcolor=ft.colors.SURFACE,
        border=ft.border.all(1, ft.colors.OUTLINE_VARIANT),
    )

    return ft.View(
        "/",
        controls=[
            ft.Container(
                content=ft.ResponsiveRow([
                    ft.Column(col={"xs": 12, "sm": 10, "md": 6, "lg": 4}, controls=[form_card]),
                ], alignment=ft.MainAxisAlignment.CENTER),
                alignment=ft.alignment.center,
                expand=True,
                padding=20,
            )
        ],
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )
