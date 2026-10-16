from datetime import datetime, date
from typing import Callable, Optional
import flet as ft

from config import PastelTheme
from controllers.dashboard_controller import (
    DashboardController,
    DateFilterPreset,
    SPANISH_MONTHS,
)
from views.theme import create_card, create_badge, safe_update


class DateRangeFilterBar(ft.Container):
    """
    Componente de Filtrado Temporal Avanzado (Estilo YouTube Studio / Google Calendar).
    Incluye:
    - Dropdown con los 7 preajustes rápidos:
      * Hoy
      * Última Semana (Últimos 7 días)
      * Último Mes (Últimos 30 días)
      * Mes Específico (Selector de mes y año)
      * Año Específico (Selector de año)
      * Desde el inicio (All-time)
      * Personalizado (Dos DatePickers interactivos para Fecha Inicio y Fecha Fin)
    - Sincronización reactiva con DashboardController.
    """

    def __init__(
        self,
        dashboard_controller: DashboardController,
        on_range_changed: Optional[Callable[[Optional[datetime], Optional[datetime], str], None]] = None,
    ):
        super().__init__()
        self.controller = dashboard_controller
        self.on_range_changed = on_range_changed

        now = datetime.now()
        current_year = now.year
        years_list = [str(y) for y in range(current_year - 5, current_year + 3)]

        # 1. Dropdown Principal de Preajustes (Estilo YouTube Studio)
        self.preset_dropdown = ft.Dropdown(
            label="Periodo de Análisis",
            value=self.controller.current_preset,
            width=255,
            dense=True,
            border_radius=10,
            border_color=PastelTheme.PRIMARY,
            bgcolor=PastelTheme.SURFACE_WHITE,
            text_size=13,
            options=[
                ft.dropdown.Option(DateFilterPreset.TODAY, "Hoy"),
                ft.dropdown.Option(DateFilterPreset.LAST_7_DAYS, "Última Semana (Últimos 7 días)"),
                ft.dropdown.Option(DateFilterPreset.LAST_30_DAYS, "Último Mes (Últimos 30 días)"),
                ft.dropdown.Option(DateFilterPreset.SPECIFIC_MONTH, "Mes Específico"),
                ft.dropdown.Option(DateFilterPreset.SPECIFIC_YEAR, "Año Específico"),
                ft.dropdown.Option(DateFilterPreset.ALL_TIME, "Desde el inicio (All-time)"),
                ft.dropdown.Option(DateFilterPreset.CUSTOM, "Personalizado (Rango de fechas)"),
            ],
            on_select=self._on_preset_selected,
        )

        # 2. Selectores auxiliares para "Mes Específico" y "Año Específico"
        self.month_dropdown = ft.Dropdown(
            label="Mes",
            value=str(self.controller.selected_month),
            width=145,
            dense=True,
            border_radius=10,
            bgcolor=PastelTheme.SURFACE_WHITE,
            text_size=13,
            visible=(self.controller.current_preset == DateFilterPreset.SPECIFIC_MONTH),
            options=[
                ft.dropdown.Option(str(m_num), m_name)
                for m_num, m_name in SPANISH_MONTHS.items()
            ],
            on_select=self._on_month_or_year_changed,
        )

        self.year_dropdown = ft.Dropdown(
            label="Año",
            value=str(self.controller.selected_year),
            width=110,
            dense=True,
            border_radius=10,
            bgcolor=PastelTheme.SURFACE_WHITE,
            text_size=13,
            visible=(
                self.controller.current_preset
                in (DateFilterPreset.SPECIFIC_MONTH, DateFilterPreset.SPECIFIC_YEAR)
            ),
            options=[ft.dropdown.Option(y, y) for y in years_list],
            on_select=self._on_month_or_year_changed,
        )

        # 3. Botones disparadores de DatePickers para "Personalizado"
        self.start_date_btn_text = ft.Text(
            f"Inicio: {self.controller.custom_start_date.strftime('%Y-%m-%d')}",
            size=12,
            weight=ft.FontWeight.W_600,
        )
        self.end_date_btn_text = ft.Text(
            f"Fin: {self.controller.custom_end_date.strftime('%Y-%m-%d')}",
            size=12,
            weight=ft.FontWeight.W_600,
        )

        self.custom_dates_row = ft.Row(
            spacing=8,
            visible=(self.controller.current_preset == DateFilterPreset.CUSTOM),
            controls=[
                ft.OutlinedButton(
                    content=ft.Row(
                        spacing=6,
                        controls=[
                            ft.Icon(ft.Icons.CALENDAR_MONTH_ROUNDED, size=16, color=PastelTheme.PRIMARY),
                            self.start_date_btn_text,
                        ],
                    ),
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                    ),
                    tooltip="Seleccionar Fecha de Inicio",
                    on_click=self._open_start_date_picker,
                ),
                ft.Icon(ft.Icons.ARROW_FORWARD_ROUNDED, size=16, color=PastelTheme.TEXT_MUTED),
                ft.OutlinedButton(
                    content=ft.Row(
                        spacing=6,
                        controls=[
                            ft.Icon(ft.Icons.EVENT_ROUNDED, size=16, color=PastelTheme.PRIMARY),
                            self.end_date_btn_text,
                        ],
                    ),
                    style=ft.ButtonStyle(
                        shape=ft.RoundedRectangleBorder(radius=8),
                        padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                    ),
                    tooltip="Seleccionar Fecha de Fin",
                    on_click=self._open_end_date_picker,
                ),
            ],
        )

        # 4. Etiqueta informativa del rango activo
        _, _, init_label = self.controller.get_active_date_range()
        self.active_range_text = ft.Text(
            init_label,
            size=12,
            weight=ft.FontWeight.W_600,
            color=PastelTheme.PRIMARY,
        )

        self.content = create_card(
            padding=12,
            bg_color=PastelTheme.SURFACE_WHITE,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                wrap=True,
                spacing=12,
                controls=[
                    ft.Row(
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        wrap=True,
                        controls=[
                            ft.Container(
                                bgcolor=PastelTheme.PRIMARY_PASTEL,
                                border_radius=10,
                                padding=8,
                                content=ft.Icon(
                                    ft.Icons.DATE_RANGE_ROUNDED,
                                    color=PastelTheme.PRIMARY,
                                    size=20,
                                ),
                            ),
                            self.preset_dropdown,
                            self.month_dropdown,
                            self.year_dropdown,
                            self.custom_dates_row,
                        ],
                    ),
                    ft.Container(
                        bgcolor=PastelTheme.PRIMARY_PASTEL,
                        border_radius=8,
                        padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                        content=ft.Row(
                            spacing=6,
                            tight=True,
                            controls=[
                                ft.Icon(ft.Icons.SCHEDULE_ROUNDED, size=15, color=PastelTheme.PRIMARY),
                                self.active_range_text,
                            ],
                        ),
                    ),
                ],
            ),
        )

    def sync_from_controller(self) -> None:
        """Sincroniza los controles visuales con el estado actual del controlador."""
        preset = self.controller.current_preset
        self.preset_dropdown.value = preset
        self.month_dropdown.value = str(self.controller.selected_month)
        self.year_dropdown.value = str(self.controller.selected_year)
        self.month_dropdown.visible = (preset == DateFilterPreset.SPECIFIC_MONTH)
        self.year_dropdown.visible = (
            preset in (DateFilterPreset.SPECIFIC_MONTH, DateFilterPreset.SPECIFIC_YEAR)
        )
        self.custom_dates_row.visible = (preset == DateFilterPreset.CUSTOM)
        self.start_date_btn_text.value = f"Inicio: {self.controller.custom_start_date.strftime('%Y-%m-%d')}"
        self.end_date_btn_text.value = f"Fin: {self.controller.custom_end_date.strftime('%Y-%m-%d')}"

        _, _, label = self.controller.get_active_date_range()
        self.active_range_text.value = label
        safe_update(self)

    def _on_preset_selected(self, e) -> None:
        preset = self.preset_dropdown.value or DateFilterPreset.ALL_TIME
        self.month_dropdown.visible = (preset == DateFilterPreset.SPECIFIC_MONTH)
        self.year_dropdown.visible = (
            preset in (DateFilterPreset.SPECIFIC_MONTH, DateFilterPreset.SPECIFIC_YEAR)
        )
        self.custom_dates_row.visible = (preset == DateFilterPreset.CUSTOM)

        start_dt, end_dt, label = self.controller.set_filter_preset(
            preset=preset,
            year=int(self.year_dropdown.value or datetime.now().year),
            month=int(self.month_dropdown.value or datetime.now().month),
        )
        self.active_range_text.value = label
        safe_update(self)

        # Si el usuario selecciona "Personalizado", abrimos automáticamente el primer DatePicker
        if preset == DateFilterPreset.CUSTOM:
            self._open_start_date_picker(chain_end_picker=True)

        if self.on_range_changed:
            self.on_range_changed(start_dt, end_dt, label)

    def _on_month_or_year_changed(self, e) -> None:
        preset = self.preset_dropdown.value or self.controller.current_preset
        year_val = int(self.year_dropdown.value or datetime.now().year)
        month_val = int(self.month_dropdown.value or datetime.now().month)

        start_dt, end_dt, label = self.controller.set_filter_preset(
            preset=preset,
            year=year_val,
            month=month_val,
        )
        self.active_range_text.value = label
        safe_update(self)

        if self.on_range_changed:
            self.on_range_changed(start_dt, end_dt, label)

    @staticmethod
    def _extract_date(raw_val) -> Optional[date]:
        if raw_val is None:
            return None
        if isinstance(raw_val, datetime):
            return raw_val.date()
        if isinstance(raw_val, date):
            return raw_val
        if isinstance(raw_val, str):
            try:
                return datetime.fromisoformat(raw_val[:10]).date()
            except Exception:
                return None
        return None

    def _open_start_date_picker(self, _=None, chain_end_picker: bool = False) -> None:
        if not self.page:
            return

        def on_start_picked(ev):
            picked = self._extract_date(ev.control.value)
            if picked:
                self.controller.custom_start_date = picked
                if self.controller.custom_end_date < picked:
                    self.controller.custom_end_date = picked
                self.start_date_btn_text.value = f"Inicio: {self.controller.custom_start_date.strftime('%Y-%m-%d')}"
                self.end_date_btn_text.value = f"Fin: {self.controller.custom_end_date.strftime('%Y-%m-%d')}"
                start_dt, end_dt, label = self.controller.set_filter_preset(
                    preset=DateFilterPreset.CUSTOM,
                    custom_start=self.controller.custom_start_date,
                    custom_end=self.controller.custom_end_date,
                )
                self.active_range_text.value = label
                safe_update(self)
                if self.on_range_changed:
                    self.on_range_changed(start_dt, end_dt, label)

                if chain_end_picker:
                    self._open_end_date_picker()

        try:
            picker = ft.DatePicker(
                value=self.controller.custom_start_date,
                first_date=date(2020, 1, 1),
                last_date=date(2035, 12, 31),
                help_text="Seleccione la Fecha de Inicio",
                cancel_text="Cancelar",
                confirm_text="Confirmar Inicio",
                on_change=on_start_picked,
            )
            self.page.show_dialog(picker)
        except Exception as err:
            print(f"[DateRangeFilterBar] Error abriendo DatePicker de inicio: {err}")

    def _open_end_date_picker(self, _=None) -> None:
        if not self.page:
            return

        def on_end_picked(ev):
            picked = self._extract_date(ev.control.value)
            if picked:
                self.controller.custom_end_date = picked
                if self.controller.custom_start_date > picked:
                    self.controller.custom_start_date = picked
                self.start_date_btn_text.value = f"Inicio: {self.controller.custom_start_date.strftime('%Y-%m-%d')}"
                self.end_date_btn_text.value = f"Fin: {self.controller.custom_end_date.strftime('%Y-%m-%d')}"
                start_dt, end_dt, label = self.controller.set_filter_preset(
                    preset=DateFilterPreset.CUSTOM,
                    custom_start=self.controller.custom_start_date,
                    custom_end=self.controller.custom_end_date,
                )
                self.active_range_text.value = label
                safe_update(self)
                if self.on_range_changed:
                    self.on_range_changed(start_dt, end_dt, label)

        try:
            picker = ft.DatePicker(
                value=self.controller.custom_end_date,
                first_date=date(2020, 1, 1),
                last_date=date(2035, 12, 31),
                help_text="Seleccione la Fecha de Fin",
                cancel_text="Cancelar",
                confirm_text="Aplicar Rango",
                on_change=on_end_picked,
            )
            self.page.show_dialog(picker)
        except Exception as err:
            print(f"[DateRangeFilterBar] Error abriendo DatePicker de fin: {err}")
