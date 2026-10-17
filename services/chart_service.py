import base64
import io
from typing import Dict, Union, Optional
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


class ChartService:
    """
    Servicio de generación de gráficos analíticos estilizados en tonos pastel
    para integración directa en la interfaz Flet como imágenes (bytes o Base64).
    """

    PASTEL_PALETTE = [
        "#93C5FD",  # Azul pastel
        "#86EFAC",  # Verde menta pastel
        "#FDE047",  # Amarillo suave
        "#FCA5A5",  # Coral / Rosado pastel
        "#C4B5FD",  # Lavanda pastel
        "#FDBA74",  # Melocotón pastel
        "#67E8F9",  # Cyan suave
    ]

    @staticmethod
    def generate_valuation_bar_chart(
        cost_val: float,
        retail_val: float,
        profit_val: float,
        realized_sales_val: Optional[float] = None,
        period_label: str = "",
        as_bytes: bool = True
    ) -> Union[bytes, str]:
        """
        Genera gráfico de barras comparativo para el periodo seleccionado:
        Costos/Egresos vs. Ventas Realizadas vs. Venta Proyectada vs. Utilidad Real.
        """
        fig, ax = plt.subplots(figsize=(5.8, 3.6), dpi=100)
        fig.patch.set_facecolor("#FFFFFF")
        ax.set_facecolor("#FFFFFF")

        if realized_sales_val is not None:
            labels = ["Costos/Egresos", "Ventas Real.", "Venta Proy.", "Utilidad Real"]
            values = [cost_val, realized_sales_val, retail_val, profit_val]
            profit_color = "#86EFAC" if profit_val >= 0 else "#FCA5A5"
            colors = ["#FCA5A5", "#93C5FD", "#C4B5FD", profit_color]
        else:
            labels = ["Costos/Egresos", "Ventas", "Utilidad Real"]
            values = [cost_val, retail_val, profit_val]
            profit_color = "#86EFAC" if profit_val >= 0 else "#FCA5A5"
            colors = ["#FCA5A5", "#93C5FD", profit_color]

        bars = ax.bar(labels, values, color=colors, width=0.52, edgecolor="#CBD5E1", linewidth=1.2)

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#94A3B8")
        ax.spines["bottom"].set_color("#94A3B8")
        ax.tick_params(colors="#475569", labelsize=8.5)
        ax.yaxis.grid(True, linestyle="--", alpha=0.3, color="#CBD5E1")
        ax.axhline(0, color="#94A3B8", linewidth=0.9)

        max_abs = max([abs(v) for v in values] + [100.0])
        min_val = min(values + [0.0])
        max_val = max(values + [0.0])
        ax.set_ylim(
            min_val - (max_abs * 0.22 if min_val < 0 else 0),
            max_val + max_abs * 0.22
        )

        for bar in bars:
            height = bar.get_height()
            offset_y = 4 if height >= 0 else -14
            ax.annotate(
                f"${height:,.0f}",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, offset_y),
                textcoords="offset points",
                ha="center",
                va="bottom" if height >= 0 else "top",
                fontsize=8.5,
                fontweight="bold",
                color="#0F172A" if height >= 0 else "#E11D48"
            )

        title = "Balance Financiero del Periodo"
        if period_label:
            ax.set_title(f"{title}\n({period_label})", fontsize=9.5, fontweight="bold", color="#0F172A", pad=10)
        else:
            ax.set_title(title, fontsize=10.5, fontweight="bold", color="#0F172A", pad=12)

        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format="png", bbox_inches="tight", dpi=100, facecolor=fig.get_facecolor(), transparent=False)
        plt.close(fig)
        data = buffer.getvalue()
        if as_bytes:
            return data
        return base64.b64encode(data).decode("utf-8")

    @staticmethod
    def generate_category_pie_chart(
        categories_dict: Dict[str, float],
        period_label: str = "",
        as_bytes: bool = True
    ) -> Union[bytes, str]:
        """
        Genera gráfico de torta mostrando la participación por categoría en el periodo seleccionado.
        """
        fig, ax = plt.subplots(figsize=(5.8, 3.6), dpi=100)
        fig.patch.set_facecolor("#FFFFFF")
        ax.set_facecolor("#FFFFFF")

        clean_dict = {k: v for k, v in (categories_dict or {}).items() if v and v > 0}

        if not clean_dict or sum(clean_dict.values()) <= 0:
            labels = ["Sin movimientos en el periodo"]
            values = [1]
            colors = ["#E2E8F0"]
            has_data = False
        else:
            # Ordenar de mayor a menor y agrupar excedentes si hay más de 6 categorías
            sorted_items = sorted(clean_dict.items(), key=lambda x: x[1], reverse=True)
            if len(sorted_items) > 6:
                top_items = sorted_items[:5]
                others_sum = sum(v for _, v in sorted_items[5:])
                top_items.append(("Otros", others_sum))
                sorted_items = top_items

            labels = [k for k, _ in sorted_items]
            values = [v for _, v in sorted_items]
            colors = (ChartService.PASTEL_PALETTE * 3)[:len(labels)]
            has_data = True

        wedges, texts, autotexts = ax.pie(
            values,
            labels=labels,
            autopct="%1.1f%%" if has_data else "",
            startangle=140,
            colors=colors,
            textprops={"fontsize": 8.5, "color": "#1E293B"},
            wedgeprops={"edgecolor": "#FFFFFF", "linewidth": 2, "antialiased": True}
        )

        for autotext in autotexts:
            autotext.set_color("#0F172A")
            autotext.set_fontsize(8)
            autotext.set_weight("bold")

        title = "Distribución por Categorías (% Valor)"
        if period_label:
            ax.set_title(f"{title}\n({period_label})", fontsize=9.5, fontweight="bold", color="#0F172A", pad=10)
        else:
            ax.set_title(title, fontsize=10.5, fontweight="bold", color="#0F172A", pad=12)

        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format="png", bbox_inches="tight", dpi=100, facecolor=fig.get_facecolor(), transparent=False)
        plt.close(fig)
        data = buffer.getvalue()
        if as_bytes:
            return data
        return base64.b64encode(data).decode("utf-8")
