import flet as ft
from config import PastelTheme

def create_card(
    content: ft.Control,
    padding: int = 16,
    bg_color: str = PastelTheme.SURFACE_WHITE,
    border_color: str = PastelTheme.BORDER_LIGHT,
    border_radius: int = PastelTheme.BORDER_RADIUS_CARD,
    expand: bool | int = False,
    visible: bool = True
) -> ft.Container:
    """Contenedor estilo Card redondeada con sombra y borde sutil."""
    return ft.Container(
        content=content,
        bgcolor=bg_color,
        border_radius=border_radius,
        border=ft.Border.all(1, border_color),
        padding=padding,
        expand=expand,
        visible=visible,
        shadow=ft.BoxShadow(
            spread_radius=0,
            blur_radius=8,
            color="#0A0F1D0A", # Sombra suave sutil
            offset=ft.Offset(0, 2),
        )
    )

def create_metric_tile(
    title: str,
    value: str,
    icon: str,
    bg_pastel: str,
    icon_color: str,
    subtitle: str = ""
) -> ft.Container:
    """Tarjeta KPI métrica con fondo pastel, icono grande y números legibles."""
    return create_card(
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Column(
                    spacing=4,
                    controls=[
                        ft.Text(title, size=13, weight=ft.FontWeight.W_500, color=PastelTheme.TEXT_SECONDARY),
                        ft.Text(value, size=22, weight=ft.FontWeight.BOLD, color=PastelTheme.TEXT_PRIMARY),
                        *( [ft.Text(subtitle, size=11, color=PastelTheme.TEXT_MUTED)] if subtitle else [] )
                    ]
                ),
                ft.Container(
                    content=ft.Icon(icon, size=28, color=icon_color),
                    bgcolor=bg_pastel,
                    border_radius=12,
                    padding=10,
                )
            ]
        ),
        padding=18,
        expand=True
    )

def create_badge(text: str, bg_color: str, text_color: str) -> ft.Container:
    """Etiqueta/Chip redondeado para estados y categorías."""
    return ft.Container(
        content=ft.Text(text, size=11, weight=ft.FontWeight.W_600, color=text_color),
        bgcolor=bg_color,
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=8, vertical=4),
    )

def safe_update(control: ft.Control) -> None:
    """Actualiza el control de forma segura si ya está montado en la página."""
    try:
        control.update()
    except Exception:
        pass


class SearchableDropdown(ft.Container):
    """
    Selector desplegable / lista deslizante con filtro instantáneo desde la 1ª letra (0ms delay).
    - Permite abrir la lista completa deslizable con un clic o con el botón desplegable (▼).
    - A medida que el usuario digita desde la primera letra, filtra en vivo las opciones
      hasta que quede una sola persona/proveedor (autoseleccionándola o permitiendo clic/Enter).
    """

    def __init__(
        self,
        label: str,
        hint_text: str = "Seleccione de la lista o escriba desde la 1ª letra...",
        prefix_icon: str = ft.Icons.PERSON_SEARCH_ROUNDED,
        options: list[dict] | None = None,
        value: str | None = None,
        on_select=None,
        visible: bool = True,
        max_list_height: int = 165,
    ):
        super().__init__(visible=visible)
        self._label = label
        self._default_hint = hint_text
        self._options: list[dict] = options or []
        self._selected_key: str | None = value
        self._on_select_callback = on_select
        self._max_list_height = max_list_height

        self.toggle_icon_btn = ft.IconButton(
            icon=ft.Icons.ARROW_DROP_DOWN_ROUNDED,
            icon_size=22,
            icon_color=PastelTheme.PRIMARY,
            tooltip="Abrir / Cerrar lista deslizante",
            style=ft.ButtonStyle(padding=ft.Padding.all(2)),
            on_click=self._on_toggle_click,
        )

        self.clear_icon_btn = ft.IconButton(
            icon=ft.Icons.CLOSE_ROUNDED,
            icon_size=16,
            icon_color=PastelTheme.TEXT_MUTED,
            tooltip="Limpiar y buscar desde la 1ª letra",
            style=ft.ButtonStyle(padding=ft.Padding.all(2)),
            visible=False,
            on_click=self._on_clear_click,
        )

        self.search_input = ft.TextField(
            label=self._label,
            hint_text=self._default_hint,
            prefix_icon=prefix_icon,
            border_radius=PastelTheme.BORDER_RADIUS_INPUT,
            bgcolor=PastelTheme.SURFACE_WHITE,
            border_color=PastelTheme.BORDER_LIGHT,
            focused_border_color=PastelTheme.PRIMARY,
            dense=True,
            text_size=13,
            suffix=ft.Row(
                spacing=0,
                tight=True,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    self.clear_icon_btn,
                    self.toggle_icon_btn,
                ],
            ),
            on_focus=self._on_input_focus,
            on_change=self._on_input_change,
            on_submit=self._on_input_submit,
        )

        self.items_column = ft.Column(
            spacing=3,
            tight=True,
            scroll=ft.ScrollMode.AUTO,
        )

        self.list_container = ft.Container(
            visible=False,
            bgcolor=PastelTheme.SURFACE_WHITE,
            border_radius=10,
            border=ft.Border.all(1, PastelTheme.PRIMARY_PASTEL),
            padding=ft.Padding.symmetric(horizontal=6, vertical=6),
            shadow=ft.BoxShadow(
                spread_radius=0,
                blur_radius=10,
                color="#18000000",
                offset=ft.Offset(0, 4),
            ),
            content=self.items_column,
        )

        self.content = ft.Column(
            spacing=4,
            tight=True,
            controls=[
                self.search_input,
                self.list_container,
            ],
        )

        if self._selected_key is not None:
            self._sync_display_from_value()

    @property
    def value(self) -> str | None:
        return self._selected_key

    @value.setter
    def value(self, new_val: str | None) -> None:
        self._selected_key = new_val
        self._sync_display_from_value()

    def set_options(self, options: list[dict], preserve_value: bool = True) -> None:
        """
        Actualiza las opciones disponibles.
        Cada opción es un dict: {'key': str, 'label': str, 'subtitle': str (opcional)}.
        """
        self._options = options or []
        if preserve_value and self._selected_key is not None:
            valid_keys = {str(o["key"]) for o in self._options}
            if str(self._selected_key) not in valid_keys:
                self._selected_key = None
        self._sync_display_from_value()
        if self.list_container.visible:
            self._render_filtered_list(self.search_input.value or "", auto_select_single=False)

    def clear_selection(self, notify: bool = False) -> None:
        self._selected_key = None
        self.search_input.value = ""
        self.search_input.hint_text = self._default_hint
        self.clear_icon_btn.visible = False
        self.list_container.visible = False
        self.toggle_icon_btn.icon = ft.Icons.ARROW_DROP_DOWN_ROUNDED
        safe_update(self)
        if notify and self._on_select_callback:
            self._on_select_callback(None)

    def _get_selected_option(self) -> dict | None:
        if self._selected_key is None:
            return None
        for opt in self._options:
            if str(opt["key"]) == str(self._selected_key):
                return opt
        return None

    def _sync_display_from_value(self) -> None:
        opt = self._get_selected_option()
        if opt:
            self.search_input.value = opt["label"]
            self.search_input.hint_text = self._default_hint
            self.clear_icon_btn.visible = True
        else:
            self.search_input.value = ""
            self.search_input.hint_text = self._default_hint
            self.clear_icon_btn.visible = False

    def _on_input_focus(self, _e=None) -> None:
        """
        Al hacer clic en el campo, abre la lista deslizante completa y prepara el campo
        para que al digitar desde la 1ª letra filtre de inmediato sin tener que borrar manualmente.
        """
        opt = self._get_selected_option()
        if opt and (self.search_input.value or "").strip() == opt["label"]:
            self.search_input.value = ""
            self.search_input.hint_text = f"Actual: {opt['label']} — Escriba desde la 1ª letra..."
        self._open_list(query=self.search_input.value or "", auto_select_single=False)

    def _on_toggle_click(self, _e=None) -> None:
        if self.list_container.visible:
            self._close_list(restore_selected_text=True)
        else:
            opt = self._get_selected_option()
            if opt and (self.search_input.value or "").strip() == opt["label"]:
                self.search_input.value = ""
                self.search_input.hint_text = f"Actual: {opt['label']} — Escriba desde la 1ª letra..."
            self._open_list(query=self.search_input.value or "", auto_select_single=False)

    def _on_clear_click(self, _e=None) -> None:
        self.search_input.value = ""
        self.search_input.hint_text = self._default_hint
        self.clear_icon_btn.visible = False
        self._open_list(query="", auto_select_single=False)

    def _on_input_change(self, _e=None) -> None:
        """
        Filtra instantáneamente (0ms) desde la primera letra digitada (len >= 1).
        Si el usuario borra todo, muestra toda la lista deslizante abierta.
        """
        query = (self.search_input.value or "").strip()
        self.clear_icon_btn.visible = bool(query) or (self._selected_key is not None)
        self._open_list(query=query, auto_select_single=True)

    def _on_input_submit(self, _e=None) -> None:
        """Al presionar Enter, selecciona la primera coincidencia visible y cierra la lista."""
        query = (self.search_input.value or "").strip()
        filtered = self._filter_options(query)
        if filtered:
            self._select_option(filtered[0])

    def _filter_options(self, query: str) -> list[dict]:
        term = (query or "").strip().lower()
        if not term:
            return list(self._options)

        matches = []
        for opt in self._options:
            label_low = (opt.get("label") or "").lower()
            sub_low = (opt.get("subtitle") or "").lower()
            if term in label_low or term in sub_low:
                matches.append(opt)

        # Priorizar opciones cuyo nombre empieza por la letra/texto digitado
        matches.sort(
            key=lambda o: (
                0 if (o.get("label") or "").lower().startswith(term) else 1,
                (o.get("label") or "").lower(),
            )
        )
        return matches

    def _open_list(self, query: str = "", auto_select_single: bool = False) -> None:
        self._render_filtered_list(query=query, auto_select_single=auto_select_single)
        self.list_container.visible = True
        self.toggle_icon_btn.icon = ft.Icons.ARROW_DROP_UP_ROUNDED
        safe_update(self)

    def _close_list(self, restore_selected_text: bool = True) -> None:
        if restore_selected_text:
            self._sync_display_from_value()
        self.list_container.visible = False
        self.toggle_icon_btn.icon = ft.Icons.ARROW_DROP_DOWN_ROUNDED
        safe_update(self)

    def _render_filtered_list(self, query: str = "", auto_select_single: bool = False) -> None:
        filtered = self._filter_options(query)
        clean_query = (query or "").strip()

        # Si el usuario está digitando (desde la 1ª letra) y queda una única opción, la pre-selecciona automáticamente
        if auto_select_single and len(clean_query) >= 1 and len(filtered) == 1:
            single_opt = filtered[0]
            if str(self._selected_key) != str(single_opt["key"]):
                self._selected_key = str(single_opt["key"])
                if self._on_select_callback:
                    self._on_select_callback(self._selected_key)

        tiles = []
        if not filtered:
            tiles.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                    content=ft.Row(
                        spacing=8,
                        controls=[
                            ft.Icon(ft.Icons.SEARCH_OFF_ROUNDED, size=16, color=PastelTheme.TEXT_MUTED),
                            ft.Text(
                                f"Sin coincidencias para «{clean_query}»",
                                size=12,
                                color=PastelTheme.TEXT_MUTED,
                                italic=True,
                            ),
                        ],
                    ),
                )
            )
        else:
            is_single_match = len(clean_query) >= 1 and len(filtered) == 1
            for opt in filtered:
                is_selected = (self._selected_key is not None and str(opt["key"]) == str(self._selected_key))
                subtitle_text = (opt.get("subtitle") or "").strip()

                right_controls = []
                if is_single_match:
                    right_controls.append(
                        create_badge("✓ Único resultado", PastelTheme.MINT_PASTEL, PastelTheme.ACCENT_MINT)
                    )
                elif is_selected:
                    right_controls.append(
                        ft.Icon(ft.Icons.CHECK_CIRCLE_ROUNDED, size=17, color=PastelTheme.ACCENT_MINT)
                    )

                tiles.append(
                    ft.Container(
                        bgcolor=PastelTheme.PRIMARY_PASTEL if (is_selected or is_single_match) else PastelTheme.SURFACE_VARIANT,
                        border_radius=8,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=7),
                        ink=True,
                        on_click=lambda _, o=opt: self._select_option(o),
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            controls=[
                                ft.Column(
                                    spacing=1,
                                    expand=True,
                                    controls=[
                                        ft.Text(
                                            opt["label"],
                                            size=12,
                                            weight=ft.FontWeight.BOLD if (is_selected or is_single_match) else ft.FontWeight.W_600,
                                            color=PastelTheme.PRIMARY if (is_selected or is_single_match) else PastelTheme.TEXT_PRIMARY,
                                        ),
                                        *(
                                            [
                                                ft.Text(
                                                    subtitle_text,
                                                    size=11,
                                                    color=PastelTheme.TEXT_SECONDARY,
                                                )
                                            ]
                                            if subtitle_text
                                            else []
                                        ),
                                    ],
                                ),
                                *right_controls,
                            ],
                        ),
                    )
                )

        self.items_column.controls = tiles
        # Ajustar altura máxima de la lista deslizante para que tenga scroll cuando hay varios elementos
        row_count = max(1, len(tiles))
        estimated_height = min(self._max_list_height, row_count * 44 + 8)
        self.list_container.height = estimated_height if len(tiles) > 3 else None

    def _select_option(self, opt: dict) -> None:
        self._selected_key = str(opt["key"])
        self.search_input.value = opt["label"]
        self.search_input.hint_text = self._default_hint
        self.clear_icon_btn.visible = True
        self.list_container.visible = False
        self.toggle_icon_btn.icon = ft.Icons.ARROW_DROP_DOWN_ROUNDED
        safe_update(self)
        if self._on_select_callback:
            self._on_select_callback(self._selected_key)

