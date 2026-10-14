import customtkinter as ctk

class SettingsModule(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        self.lbl_title = ctk.CTkLabel(self, text="Ajustes de Sistema", font=ctk.CTkFont(weight="bold"))
        self.lbl_title.grid(row=0, column=0, pady=30)
        
        self.settings_frame = ctk.CTkFrame(self)
        self.settings_frame.grid(row=1, column=0, padx=40, pady=10, sticky="ew")
        self.settings_frame.grid_columnconfigure(1, weight=1)
        
        self.lbl_font_desc = ctk.CTkLabel(self.settings_frame, text="Tamaño de Fuente Global (Accesibilidad):")
        self.lbl_font_desc.grid(row=0, column=0, padx=20, pady=30, sticky="w")
        
        # Slider para cambiar tamaño de fuente en tiempo real
        self.font_slider = ctk.CTkSlider(self.settings_frame, from_=10, to=24, number_of_steps=14, command=self.on_slider_change)
        self.font_slider.set(self.controller.base_font_size)
        self.font_slider.grid(row=0, column=1, padx=20, pady=30, sticky="ew")
        
        self.lbl_font_val = ctk.CTkLabel(self.settings_frame, text=f"{self.controller.base_font_size} px")
        self.lbl_font_val.grid(row=0, column=2, padx=20, pady=30)

    def on_slider_change(self, value):
        size = int(value)
        self.lbl_font_val.configure(text=f"{size} px")
        # LLamada a la actualización global en el controlador principal
        self.controller.update_global_font_size(size)

    def update_font_size(self, size):
        self.lbl_title.configure(font=ctk.CTkFont(size=size + 8, weight="bold"))
        self.lbl_font_desc.configure(font=ctk.CTkFont(size=size))
        self.lbl_font_val.configure(font=ctk.CTkFont(size=size, weight="bold"))
