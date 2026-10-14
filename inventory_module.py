import customtkinter as ctk
from tkinter import ttk, messagebox

class InventoryModule(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # --- HEADER ---
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        self.lbl_title = ctk.CTkLabel(self.header_frame, text="Inventario y Administración", font=ctk.CTkFont(weight="bold"))
        self.lbl_title.pack(side="left")
        
        self.btn_delete = ctk.CTkButton(self.header_frame, text="Eliminar Producto", fg_color="#C93434", hover_color="#A32A2A", command=self.delete_product)
        self.btn_delete.pack(side="right", padx=5)
        
        self.btn_refresh = ctk.CTkButton(self.header_frame, text="Refrescar Tabla", command=self.load_data)
        self.btn_refresh.pack(side="right", padx=5)
        
        # --- DATAGRID (Treeview) ---
        self.tree_frame = ctk.CTkFrame(self)
        self.tree_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.tree_frame.grid_rowconfigure(0, weight=1)
        self.tree_frame.grid_columnconfigure(0, weight=1)
        
        self.tree = ttk.Treeview(self.tree_frame, columns=("codigo", "nombre", "desc", "p_compra", "p_venta", "stock"), show="headings")
        self.tree.heading("codigo", text="Código de Barras")
        self.tree.heading("nombre", text="Nombre")
        self.tree.heading("desc", text="Descripción")
        self.tree.heading("p_compra", text="P. Compra")
        self.tree.heading("p_venta", text="P. Venta")
        self.tree.heading("stock", text="Stock")
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        self.tree.bind("<Double-1>", self.on_double_click) # Doble click para editar
        
        # --- FORMULARIO DE REGISTRO ---
        self.form_frame = ctk.CTkFrame(self)
        self.form_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        self.form_frame.grid_columnconfigure((1, 3, 5), weight=1)
        
        self.v_codigo = ctk.StringVar()
        self.v_nombre = ctk.StringVar()
        self.v_desc = ctk.StringVar()
        self.v_pcompra = ctk.StringVar()
        self.v_pventa = ctk.StringVar()
        self.v_stock = ctk.StringVar()
        
        # Fila 1 de inputs
        ctk.CTkLabel(self.form_frame, text="Código:", anchor="e").grid(row=0, column=0, padx=5, pady=10, sticky="e")
        self.e_codigo = ctk.CTkEntry(self.form_frame, textvariable=self.v_codigo)
        self.e_codigo.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        
        ctk.CTkLabel(self.form_frame, text="Nombre:", anchor="e").grid(row=0, column=2, padx=5, pady=10, sticky="e")
        self.e_nombre = ctk.CTkEntry(self.form_frame, textvariable=self.v_nombre)
        self.e_nombre.grid(row=0, column=3, padx=5, pady=10, sticky="ew")
        
        ctk.CTkLabel(self.form_frame, text="Desc:", anchor="e").grid(row=0, column=4, padx=5, pady=10, sticky="e")
        self.e_desc = ctk.CTkEntry(self.form_frame, textvariable=self.v_desc)
        self.e_desc.grid(row=0, column=5, padx=5, pady=10, sticky="ew")
        
        # Fila 2 de inputs
        ctk.CTkLabel(self.form_frame, text="P. Compra:", anchor="e").grid(row=1, column=0, padx=5, pady=10, sticky="e")
        self.e_pcompra = ctk.CTkEntry(self.form_frame, textvariable=self.v_pcompra)
        self.e_pcompra.grid(row=1, column=1, padx=5, pady=10, sticky="ew")
        
        ctk.CTkLabel(self.form_frame, text="P. Venta:", anchor="e").grid(row=1, column=2, padx=5, pady=10, sticky="e")
        self.e_pventa = ctk.CTkEntry(self.form_frame, textvariable=self.v_pventa)
        self.e_pventa.grid(row=1, column=3, padx=5, pady=10, sticky="ew")
        
        ctk.CTkLabel(self.form_frame, text="Stock Actual:", anchor="e").grid(row=1, column=4, padx=5, pady=10, sticky="e")
        self.e_stock = ctk.CTkEntry(self.form_frame, textvariable=self.v_stock)
        self.e_stock.grid(row=1, column=5, padx=5, pady=10, sticky="ew")
        
        # Botones de Formulario
        self.btn_save = ctk.CTkButton(self.form_frame, text="Guardar / Actualizar Producto", height=40, command=self.save_product)
        self.btn_save.grid(row=2, column=0, columnspan=4, pady=15, padx=10, sticky="ew")
        
        self.btn_clear_form = ctk.CTkButton(self.form_frame, text="Limpiar Formulario", height=40, fg_color="transparent", border_width=1, text_color=("gray10", "#DCE4EE"), command=self.clear_form)
        self.btn_clear_form.grid(row=2, column=4, columnspan=2, pady=15, padx=10, sticky="ew")

    def on_show(self):
        self.load_data()

    def load_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in self.controller.db.get_all_products():
            self.tree.insert("", "end", values=row)

    def on_double_click(self, event):
        selected = self.tree.selection()
        if not selected: return
        item = self.tree.item(selected[0])
        values = item['values']
        
        self.v_codigo.set(values[0])
        self.v_nombre.set(values[1])
        self.v_desc.set(values[2])
        self.v_pcompra.set(values[3])
        self.v_pventa.set(values[4])
        self.v_stock.set(values[5])

    def save_product(self):
        try:
            cod = self.v_codigo.get().strip()
            nom = self.v_nombre.get().strip()
            desc = self.v_desc.get().strip()
            pc = float(self.v_pcompra.get())
            pv = float(self.v_pventa.get())
            st = int(self.v_stock.get())
            
            if not cod or not nom:
                messagebox.showerror("Error", "El Código y el Nombre son obligatorios.")
                return
                
            existente = self.controller.db.get_product_by_code(cod)
            if existente:
                self.controller.db.update_product(cod, nom, desc, pc, pv, st)
                messagebox.showinfo("Éxito", "Producto actualizado correctamente.")
            else:
                self.controller.db.add_product(cod, nom, desc, pc, pv, st)
                messagebox.showinfo("Éxito", "Nuevo producto agregado al inventario.")
                
            self.clear_form()
            self.load_data()
        except ValueError:
            messagebox.showerror("Error de Formato", "Asegúrese de ingresar números válidos en los campos de Precios y Stock.")

    def delete_product(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Atención", "Debe seleccionar un producto de la tabla para eliminar.")
            return
        item = self.tree.item(selected[0])
        codigo = item['values'][0]
        nombre = item['values'][1]
        
        if messagebox.askyesno("Confirmar Eliminación", f"¿Está seguro que desea eliminar '{nombre}'?"):
            self.controller.db.delete_product(codigo)
            self.load_data()

    def clear_form(self):
        self.v_codigo.set("")
        self.v_nombre.set("")
        self.v_desc.set("")
        self.v_pcompra.set("")
        self.v_pventa.set("")
        self.v_stock.set("")

    def update_font_size(self, size):
        self.lbl_title.configure(font=ctk.CTkFont(size=size + 6, weight="bold"))
        self.btn_refresh.configure(font=ctk.CTkFont(size=size))
        self.btn_delete.configure(font=ctk.CTkFont(size=size))
        
        self.btn_save.configure(font=ctk.CTkFont(size=size, weight="bold"))
        self.btn_clear_form.configure(font=ctk.CTkFont(size=size))
        
        # Ajustar fuente de labels e inputs
        for child in self.form_frame.winfo_children():
            if isinstance(child, ctk.CTkLabel):
                child.configure(font=ctk.CTkFont(size=size))
            elif isinstance(child, ctk.CTkEntry):
                child.configure(font=ctk.CTkFont(size=size))
