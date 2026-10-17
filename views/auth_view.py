from typing import Callable, Optional, Dict, Any
import flet as ft

from config import PastelTheme, APP_TITLE, APP_VERSION
from controllers.auth_controller import AuthController
from views.theme import create_badge, safe_update


class AuthView(ft.Container):
    """
    Vista de Autenticación Multi-Tenant (Pantallas de 'Iniciar Sesión' y 'Crear Cuenta Nueva').
    - Diseñada con fondos claros, acentos pastel, tarjeta central flotante con bordes muy redondeados (24px),
      inputs amplios y modernos, y botón de acción con ligero sombreado (box-shadow).
    - Al iniciar la aplicación, es la única vista renderizada (menú lateral y Dashboard ocultos).
    """

    def __init__(
        self,
        auth_controller: AuthController,
        on_auth_success: Callable[[Dict[str, Any]], None],
    ):
        super().__init__(
            expand=True,
            bgcolor=PastelTheme.BG_LIGHT,
            alignment=ft.Alignment.CENTER,
            padding=24,
        )
        self.auth_ctrl = auth_controller
        self.on_auth_success = on_auth_success
        self.mode: str = "LOGIN"  # "LOGIN" o "REGISTER"

        # Cabecera dinámica de la tarjeta
        self.header_icon = ft.Icon(
            ft.Icons.POINT_OF_SALE_ROUNDED,
            size=34,
            color=PastelTheme.ACCENT_CORAL,
        )
        self.header_icon_box = ft.Container(
            bgcolor=PastelTheme.CORAL_PASTEL,
            border_radius=18,
            padding=14,
            content=self.header_icon,
        )
        self.screen_title = ft.Text(
            "Iniciar Sesión",
            size=26,
            weight=ft.FontWeight.BOLD,
            color=PastelTheme.TEXT_PRIMARY,
            text_align=ft.TextAlign.CENTER,
        )
        self.screen_subtitle = ft.Text(
            "Ingresa a tu entorno privado de Inventario y Facturación POS",
            size=13,
            color=PastelTheme.TEXT_SECONDARY,
            text_align=ft.TextAlign.CENTER,
        )

        # Inputs de texto amplios y modernos
        self.username_input = ft.TextField(
            label="Nombre de Usuario",
            hint_text="Ej. andres_tienda",
            prefix_icon=ft.Icons.PERSON_OUTLINE_ROUNDED,
            border_radius=14,
            bgcolor=PastelTheme.SURFACE_VARIANT,
            border_color=PastelTheme.BORDER_LIGHT,
            focused_border_color=PastelTheme.ACCENT_CORAL,
            text_size=14,
            content_padding=ft.Padding.symmetric(horizontal=18, vertical=16),
            autofocus=True,
            on_submit=lambda _: self._handle_submit(),
        )

        self.password_input = ft.TextField(
            label="Contraseña",
            hint_text="Ingresa tu contraseña segura...",
            prefix_icon=ft.Icons.LOCK_OUTLINE_ROUNDED,
            password=True,
            can_reveal_password=True,
            border_radius=14,
            bgcolor=PastelTheme.SURFACE_VARIANT,
            border_color=PastelTheme.BORDER_LIGHT,
            focused_border_color=PastelTheme.ACCENT_CORAL,
            text_size=14,
            content_padding=ft.Padding.symmetric(horizontal=18, vertical=16),
            on_submit=lambda _: self._handle_submit(),
        )

        self.confirm_password_input = ft.TextField(
            label="Confirmar Contraseña",
            hint_text="Repite tu contraseña para verificar...",
            prefix_icon=ft.Icons.VERIFIED_USER_OUTLINED,
            password=True,
            can_reveal_password=True,
            border_radius=14,
            bgcolor=PastelTheme.SURFACE_VARIANT,
            border_color=PastelTheme.BORDER_LIGHT,
            focused_border_color=PastelTheme.PRIMARY,
            text_size=14,
            content_padding=ft.Padding.symmetric(horizontal=18, vertical=16),
            visible=False,
            on_submit=lambda _: self._handle_submit(),
        )

        # Banner de mensajes de error o éxito
        self.feedback_icon = ft.Icon(
            ft.Icons.ERROR_OUTLINE_ROUNDED,
            size=18,
            color=PastelTheme.ACCENT_CORAL,
        )
        self.feedback_text = ft.Text(
            "",
            size=12,
            weight=ft.FontWeight.W_600,
            color=PastelTheme.ACCENT_CORAL,
            expand=True,
        )
        self.feedback_container = ft.Container(
            visible=False,
            bgcolor=PastelTheme.CORAL_PASTEL,
            border_radius=12,
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            border=ft.Border.all(1, PastelTheme.ACCENT_CORAL),
            content=ft.Row(
                spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    self.feedback_icon,
                    self.feedback_text,
                ],
            ),
        )

        # Botón principal llamativo con ligero sombreado (box-shadow) y tono rojizo/coral pastel intenso
        self.submit_btn_icon = ft.Icon(
            ft.Icons.LOGIN_ROUNDED,
            size=20,
            color=PastelTheme.TEXT_ON_PRIMARY,
        )
        self.submit_btn_label = ft.Text(
            "INGRESAR AL SISTEMA",
            size=14,
            weight=ft.FontWeight.BOLD,
            color=PastelTheme.TEXT_ON_PRIMARY,
        )
        self.submit_button = ft.Container(
            bgcolor=PastelTheme.ACCENT_CORAL,
            border_radius=14,
            padding=ft.Padding.symmetric(vertical=15, horizontal=20),
            ink=True,
            alignment=ft.Alignment.CENTER,
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=14,
                color="#40F43F5E",
                offset=ft.Offset(0, 5),
            ),
            on_click=lambda _: self._handle_submit(),
            content=ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=10,
                controls=[
                    self.submit_btn_icon,
                    self.submit_btn_label,
                ],
            ),
        )

        # Botón/enlace sutil debajo del formulario para alternar entre Login y Registro
        self.switch_prompt_text = ft.Text(
            "¿Aún no tienes una cuenta?",
            size=13,
            color=PastelTheme.TEXT_SECONDARY,
        )
        self.switch_mode_button = ft.TextButton(
            content=ft.Text(
                "Crear Cuenta Nueva",
                size=13,
                weight=ft.FontWeight.BOLD,
                color=PastelTheme.PRIMARY,
            ),
            on_click=self._toggle_mode,
        )

        # Nota informativa de aislamiento Multi-Tenant
        self.tenant_info_banner = ft.Container(
            bgcolor=PastelTheme.PRIMARY_PASTEL,
            border_radius=12,
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            content=ft.Row(
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.SHIELD_OUTLINED, size=18, color=PastelTheme.PRIMARY),
                    ft.Text(
                        "Aislamiento Multi-Tenant: Cada cuenta opera sobre su propia base de datos privada y encriptada.",
                        size=11,
                        color=PastelTheme.TEXT_SECONDARY,
                        expand=True,
                    ),
                ],
            ),
        )

        # Tarjeta central flotante con bordes muy redondeados (24px) y sombra suave
        self.auth_card = ft.Container(
            width=450,
            bgcolor=PastelTheme.SURFACE_WHITE,
            border_radius=24,
            border=ft.Border.all(1, PastelTheme.BORDER_LIGHT),
            padding=ft.Padding.symmetric(horizontal=36, vertical=34),
            shadow=ft.BoxShadow(
                spread_radius=2,
                blur_radius=28,
                color="#140F172A",
                offset=ft.Offset(0, 10),
            ),
            content=ft.Column(
                tight=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=16,
                controls=[
                    # Badge superior de versión y marca
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        spacing=6,
                        controls=[
                            create_badge(f"{APP_TITLE} v{APP_VERSION}", PastelTheme.SKY_PASTEL, PastelTheme.ACCENT_SKY),
                            create_badge("Multi-Tenant SQL", PastelTheme.MINT_PASTEL, PastelTheme.ACCENT_MINT),
                        ],
                    ),
                    self.header_icon_box,
                    ft.Column(
                        spacing=4,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[
                            self.screen_title,
                            self.screen_subtitle,
                        ],
                    ),
                    ft.Divider(height=4, color=PastelTheme.BORDER_LIGHT),
                    # Campos del formulario
                    ft.Column(
                        spacing=14,
                        horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
                        controls=[
                            self.username_input,
                            self.password_input,
                            self.confirm_password_input,
                        ],
                    ),
                    self.feedback_container,
                    self.submit_button,
                    self.tenant_info_banner,
                    # Enlace sutil para alternar entre Iniciar Sesión y Crear Cuenta Nueva
                    ft.Row(
                        alignment=ft.MainAxisAlignment.CENTER,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=4,
                        controls=[
                            self.switch_prompt_text,
                            self.switch_mode_button,
                        ],
                    ),
                ],
            ),
        )

        self.content = self.auth_card

    def reset_for_login(self, message: Optional[str] = None) -> None:
        """Restablece el formulario en modo 'Iniciar Sesión' (por ejemplo, tras Cerrar Sesión)."""
        self.mode = "LOGIN"
        self.username_input.value = ""
        self.password_input.value = ""
        self.confirm_password_input.value = ""
        self._apply_mode_ui()
        if message:
            self._show_feedback(message, is_error=False)
        else:
            self.feedback_container.visible = False
        safe_update(self)

    def _toggle_mode(self, _e=None) -> None:
        """Alterna entre las pantallas 'Iniciar Sesión' y 'Crear Cuenta Nueva'."""
        self.mode = "REGISTER" if self.mode == "LOGIN" else "LOGIN"
        self.password_input.value = ""
        self.confirm_password_input.value = ""
        self.feedback_container.visible = False
        self._apply_mode_ui()
        safe_update(self)

    def _apply_mode_ui(self) -> None:
        is_login = (self.mode == "LOGIN")

        if is_login:
            self.screen_title.value = "Iniciar Sesión"
            self.screen_subtitle.value = "Ingresa a tu entorno privado de Inventario y Facturación POS"
            self.header_icon.name = ft.Icons.POINT_OF_SALE_ROUNDED
            self.header_icon.color = PastelTheme.ACCENT_CORAL
            self.header_icon_box.bgcolor = PastelTheme.CORAL_PASTEL
            self.confirm_password_input.visible = False

            self.submit_btn_icon.name = ft.Icons.LOGIN_ROUNDED
            self.submit_btn_label.value = "INGRESAR AL SISTEMA"
            self.submit_button.bgcolor = PastelTheme.ACCENT_CORAL
            self.submit_button.shadow = ft.BoxShadow(
                spread_radius=0,
                blur_radius=14,
                color="#40F43F5E",
                offset=ft.Offset(0, 5),
            )

            self.switch_prompt_text.value = "¿Aún no tienes una cuenta?"
            self.switch_mode_button.content = ft.Text(
                "Crear Cuenta Nueva",
                size=13,
                weight=ft.FontWeight.BOLD,
                color=PastelTheme.PRIMARY,
            )
        else:
            self.screen_title.value = "Crear Cuenta Nueva"
            self.screen_subtitle.value = "Genera tu base de datos exclusiva (Inventario, Facturas y Gastos desde cero)"
            self.header_icon.name = ft.Icons.PERSON_ADD_ALT_1_ROUNDED
            self.header_icon.color = PastelTheme.PRIMARY
            self.header_icon_box.bgcolor = PastelTheme.PRIMARY_PASTEL
            self.confirm_password_input.visible = True

            self.submit_btn_icon.name = ft.Icons.ROCKET_LAUNCH_ROUNDED
            self.submit_btn_label.value = "CREAR CUENTA Y COMENZAR"
            self.submit_button.bgcolor = PastelTheme.PRIMARY
            self.submit_button.shadow = ft.BoxShadow(
                spread_radius=0,
                blur_radius=14,
                color="#404F46E5",
                offset=ft.Offset(0, 5),
            )

            self.switch_prompt_text.value = "¿Ya tienes una cuenta registrada?"
            self.switch_mode_button.content = ft.Text(
                "Iniciar Sesión",
                size=13,
                weight=ft.FontWeight.BOLD,
                color=PastelTheme.ACCENT_CORAL,
            )

    def _show_feedback(self, message: str, is_error: bool = True) -> None:
        self.feedback_text.value = message
        if is_error:
            self.feedback_container.bgcolor = PastelTheme.CORAL_PASTEL
            self.feedback_container.border = ft.Border.all(1, PastelTheme.ACCENT_CORAL)
            self.feedback_icon.name = ft.Icons.ERROR_OUTLINE_ROUNDED
            self.feedback_icon.color = PastelTheme.ACCENT_CORAL
            self.feedback_text.color = PastelTheme.ACCENT_CORAL
        else:
            self.feedback_container.bgcolor = PastelTheme.MINT_PASTEL
            self.feedback_container.border = ft.Border.all(1, PastelTheme.ACCENT_MINT)
            self.feedback_icon.name = ft.Icons.CHECK_CIRCLE_OUTLINE_ROUNDED
            self.feedback_icon.color = PastelTheme.ACCENT_MINT
            self.feedback_text.color = PastelTheme.ACCENT_MINT

        self.feedback_container.visible = True
        safe_update(self.feedback_container)

    def _handle_submit(self) -> None:
        username = (self.username_input.value or "").strip()
        password = self.password_input.value or ""

        if self.mode == "LOGIN":
            ok, msg, user_data = self.auth_ctrl.login(username=username, password=password)
            if not ok or not user_data:
                self._show_feedback(msg, is_error=True)
                return
            self.feedback_container.visible = False
            self.on_auth_success(user_data)
        else:
            confirm_pw = self.confirm_password_input.value or ""
            ok, msg, user_data = self.auth_ctrl.register(
                username=username,
                password=password,
                confirm_password=confirm_pw,
            )
            if not ok or not user_data:
                self._show_feedback(msg, is_error=True)
                return
            self.feedback_container.visible = False
            self.on_auth_success(user_data)
