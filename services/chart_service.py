import base64
import io
from typing import Dict, Union
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
        as_bytes: bool = True
    ) -> Union[bytes, str]:
        """
        Genera gráfico de barras comparativo: Costo Invertido vs. Venta Proyectada vs. Utilidad Estimada.
        """
        fig, ax = plt.subplots(figsize=(5.5, 3.6), dpi=100)
        fig.patch.set_facecolor("#FFFFFF")
        ax.set_facecolor("#FFFFFF")

        labels = ["Costo Total", "Venta Total", "Utilidad Est."]
        values = [cost_val, retail_val, profit_val]
        colors = ["#93C5FD", "#86EFAC", "#C4B5FD"]

        bars = ax.bar(labels, values, color=colors, width=0.55, edgecolor="#CBD5E1", linewidth=1.2)

        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color("#94A3B8")
        ax.spines["bottom"].set_color("#94A3B8")
        ax.tick_params(colors="#475569", labelsize=9)
        ax.yaxis.grid(True, linestyle="--", alpha=0.3, color="#CBD5E1")

        for bar in bars:
            height = bar.get_height()
            ax.annotate(
                f"${height:,.0f}",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 4),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=9,
                fontweight="bold",
                color="#0F172A"
            )

        ax.set_title("Valoración Financiera del Inventario", fontsize=11, fontweight="bold", color="#0F172A", pad=12)
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
        as_bytes: bool = True
    ) -> Union[bytes, str]:
        """
        Genera gráfico de torta mostrando la distribución del valor de inventario por categoría.
        """
        fig, ax = plt.subplots(figsize=(5.5, 3.6), dpi=100)
        fig.patch.set_facecolor("#FFFFFF")
        ax.set_facecolor("#FFFFFF")

        if not categories_dict or sum(categories_dict.values()) == 0:
            labels = ["Sin datos"]
            values = [1]
            colors = ["#E2E8F0"]
        else:
            labels = list(categories_dict.keys())
            values = list(categories_dict.values())
            colors = (ChartService.PASTEL_PALETTE * 3)[:len(labels)]

        wedges, texts, autotexts = ax.pie(
            values,
            labels=labels,
            autopct="%1.1f%%" if sum(values) > 0 and len(labels) > 0 and labels[0] != "Sin datos" else "",
            startangle=140,
            colors=colors,
            textprops={"fontsize": 9, "color": "#1E293B"},
            wedgeprops={"edgecolor": "#FFFFFF", "linewidth": 2, "antialiased": True}
        )

        for autotext in autotexts:
            autotext.set_color("#0F172A")
            autotext.set_fontsize(8.5)
            autotext.set_weight("bold")

        ax.set_title("Participación por Categorías (% Valor)", fontsize=11, fontweight="bold", color="#0F172A", pad=12)
        plt.tight_layout()

        buffer = io.BytesIO()
        plt.savefig(buffer, format="png", bbox_inches="tight", dpi=100, facecolor=fig.get_facecolor(), transparent=False)
        plt.close(fig)
        data = buffer.getvalue()
        if as_bytes:
            return data
        return base64.b64encode(data).decode("utf-8")
