import customtkinter as ctk

class KioskModule(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        # Layout centrado
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Mensaje gigante en pantalla completa
        self.lbl_main = ctk.CTkLabel(self, text="ESCANEÉ EL CÓDIGO DE BARRAS\nDEL PRODUCTO", 
                                     font=ctk.CTkFont(size=45, weight="bold"))
        self.lbl_main.grid(row=1, column=0)
        
        # Input oculto para recibir los escaneos
        self.barcode_var = ctk.StringVar()
        self.entry_barcode = ctk.CTkEntry(self, textvariable=self.barcode_var)
        self.entry_barcode.place(x=-1000, y=-1000)
        
        # Captura de Enter (\n) emitido por el escáner
        self.entry_barcode.bind("<Return>", self.on_scan)
        
        self.reset_timer = None

    def on_show(self):
        """Prepara el kiosco para la lectura de clientes"""
        self.reset_screen()
        self.entry_barcode.focus_set()

    def on_scan(self, event):
        codigo = self.barcode_var.get().strip()
        self.barcode_var.set("")
        if not codigo: return
        
        producto = self.controller.db.get_product_by_code(codigo)
        if producto:
            nombre = producto[1].upper()
            precio = producto[4]
            # Mostrar precio en grande
            self.lbl_main.configure(text=f"{nombre}\n\nPRECIO: ${precio:.2f}", text_color="#2FA572", font=ctk.CTkFont(size=65, weight="bold"))
        else:
            # Producto no encontrado
            self.lbl_main.configure(text="PRODUCTO NO ENCONTRADO", text_color="#C93434", font=ctk.CTkFont(size=45, weight="bold"))
            
        # Temporizador para regresar al mensaje inicial después de 5 segundos
        if self.reset_timer:
            self.after_cancel(self.reset_timer)
        self.reset_timer = self.after(5000, self.reset_screen)
        
        # Recuperar foco inmediatamente para siguientes lecturas
        self.entry_barcode.focus_set()

    def reset_screen(self):
        """Vuelve al estado inicial del kiosco"""
        self.lbl_main.configure(text="ESCANEÉ EL CÓDIGO DE BARRAS\nDEL PRODUCTO", text_color=("gray10", "#DCE4EE"), font=ctk.CTkFont(size=45, weight="bold"))
        self.entry_barcode.focus_set()

    def update_font_size(self, size):
        # El Kiosco debe mantener su fuente gigante por diseño para los clientes.
        # Por lo tanto, intencionalmente no modificamos la fuente aquí usando el tamaño base global.
        pass
