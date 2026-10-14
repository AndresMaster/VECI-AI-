import customtkinter as ctk
from tkinter import ttk, messagebox

class POSModule(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        # Layout del POS: 2/3 Izquierda (Tabla), 1/3 Derecha (Totales)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=1)
        
        # --- PANEL IZQUIERDO (Productos Escaneados) ---
        self.left_panel = ctk.CTkFrame(self)
        self.left_panel.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        self.left_panel.grid_rowconfigure(1, weight=1)
        self.left_panel.grid_columnconfigure(0, weight=1)
        
        self.lbl_title = ctk.CTkLabel(self.left_panel, text="Caja Registradora", font=ctk.CTkFont(weight="bold"))
        self.lbl_title.grid(row=0, column=0, pady=10)
        
        # Usamos ttk.Treeview para la tabla de productos
        style = ttk.Style()
        style.theme_use("default")
        
        self.tree = ttk.Treeview(self.left_panel, columns=("codigo", "nombre", "cantidad", "precio", "subtotal"), show="headings")
        self.tree.heading("codigo", text="Código")
        self.tree.heading("nombre", text="Nombre")
        self.tree.heading("cantidad", text="Cant.")
        self.tree.heading("precio", text="Precio Unit.")
        self.tree.heading("subtotal", text="Subtotal")
        
        self.tree.column("codigo", width=120)
        self.tree.column("nombre", width=250)
        self.tree.column("cantidad", width=80, anchor="center")
        self.tree.column("precio", width=100, anchor="e")
        self.tree.column("subtotal", width=100, anchor="e")
        
        self.tree.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        # Campo de captura para el escáner (Invisible para UI limpia, pero captura todo)
        # Se esconde desplazándolo fuera de la pantalla
        self.barcode_var = ctk.StringVar()
        self.entry_barcode = ctk.CTkEntry(self.left_panel, textvariable=self.barcode_var)
        self.entry_barcode.place(x=-1000, y=-1000)
        
        # Captura el evento 'Enter' del escáner físico
        self.entry_barcode.bind("<Return>", self.on_scan)
        
        # --- PANEL DERECHO (Totales y Pago) ---
        self.right_panel = ctk.CTkFrame(self)
        self.right_panel.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        self.lbl_total_text = ctk.CTkLabel(self.right_panel, text="TOTAL A PAGAR", font=ctk.CTkFont(weight="bold"))
        self.lbl_total_text.pack(pady=(40, 10))
        
        self.lbl_total_amount = ctk.CTkLabel(self.right_panel, text="$0.00", font=ctk.CTkFont(size=45, weight="bold"), text_color="#2FA572")
        self.lbl_total_amount.pack(pady=(0, 40))
        
        self.btn_pay = ctk.CTkButton(self.right_panel, text="Cobrar", height=70, corner_radius=10, 
                                     font=ctk.CTkFont(weight="bold"), command=self.checkout)
        self.btn_pay.pack(fill="x", padx=20, pady=10)
        
        self.btn_clear = ctk.CTkButton(self.right_panel, text="Limpiar Carrito", height=40, fg_color="transparent", 
                                       border_width=2, text_color=("gray10", "#DCE4EE"), command=self.clear_cart)
        self.btn_clear.pack(fill="x", padx=20, pady=10)
        
        # Estructura del carrito: {codigo_barras: {'producto': info, 'cantidad': x}}
        self.cart = {} 
        self.total = 0.0

    def on_show(self):
        """Asegura que el foco esté en el campo del escáner al abrir la caja"""
        self.entry_barcode.focus_set()

    def on_scan(self, event):
        """Manejador del evento del escáner de código de barras"""
        codigo = self.barcode_var.get().strip()
        self.barcode_var.set("") # Limpiar input rápido
        if not codigo: return
        
        producto = self.controller.db.get_product_by_code(codigo)
        if producto:
            if codigo in self.cart:
                self.cart[codigo]['cantidad'] += 1
            else:
                self.cart[codigo] = {
                    'producto': producto,
                    'cantidad': 1
                }
            self.update_cart_ui()
        else:
            messagebox.showwarning("Producto no encontrado", f"El código {codigo} no está registrado en el inventario.")
        
        # Recuperar foco para el siguiente escaneo
        self.entry_barcode.focus_set()

    def update_cart_ui(self):
        # Limpiar tabla
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        self.total = 0.0
        for cod, data in self.cart.items():
            prod = data['producto']
            cant = data['cantidad']
            precio = prod[4] # Índice 4 es precio_venta
            subtotal = cant * precio
            self.total += subtotal
            
            self.tree.insert("", "end", values=(cod, prod[1], cant, f"${precio:.2f}", f"${subtotal:.2f}"))
            
        self.lbl_total_amount.configure(text=f"${self.total:.2f}")

    def checkout(self):
        """Procesa el pago y descuenta el inventario"""
        if not self.cart:
            messagebox.showinfo("Caja Vacía", "No hay productos en el carrito para cobrar.")
            self.entry_barcode.focus_set()
            return
            
        # Descontar stock
        for cod, data in self.cart.items():
            self.controller.db.update_stock(cod, data['cantidad'])
            
        messagebox.showinfo("Pago Exitoso", f"Venta completada por un total de ${self.total:.2f}")
        self.clear_cart()
        
    def clear_cart(self):
        self.cart.clear()
        self.update_cart_ui()
        self.entry_barcode.focus_set()

    def update_font_size(self, size):
        """Ajuste dinámico de fuente para este módulo"""
        self.lbl_title.configure(font=ctk.CTkFont(size=size + 6, weight="bold"))
        self.lbl_total_text.configure(font=ctk.CTkFont(size=size + 8, weight="bold"))
        self.btn_pay.configure(font=ctk.CTkFont(size=size + 6, weight="bold"))
        self.btn_clear.configure(font=ctk.CTkFont(size=size))
        
        # Ajustar fuente del Treeview
        style = ttk.Style()
        style.configure("Treeview", rowheight=size * 2 + 10, font=('Arial', size))
        style.configure("Treeview.Heading", font=('Arial', size + 2, 'bold'))
