import cv2
from pyzbar import pyzbar

def escaneo_continuo(camera_index: int = 1, on_codigo_scanned=None):
    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        cap = cv2.VideoCapture(camera_index, cv2.CAP_AVFOUNDATION)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Variables de confirmación
    codigo_actual = None
    lecturas_consecutivas = 0
    lecturas_necesarias = 5
    
    # NUEVO: Lista para ir guardando todos los códigos que vayamos leyendo
    codigos_guardados = []

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

    roi_w, roi_h = 400, 200
    roi_x = (width - roi_w) // 2
    roi_y = (height - roi_h) // 2

    print("Cámara 1 iniciada. Modo de escaneo continuo ACTIVO.")
    print("Presiona la tecla 'q' en la ventana para finalizar y ver el resumen.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Error al acceder a la cámara.")
            break

        # Reiniciamos esta variable en cada frame
        codigo_confirmado = None

        # Dibujar el recuadro guía
        cv2.rectangle(frame, (roi_x, roi_y), (roi_x + roi_w, roi_y + roi_h), (255, 0, 0), 2)
        cv2.putText(frame, "Ubica el codigo aqui", (roi_x, roi_y - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

        roi_frame = frame[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w]
        gray = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
        procesado_clahe = clahe.apply(gray)

        codigos = pyzbar.decode(procesado_clahe)
        if not codigos:
            codigos = pyzbar.decode(gray)

        for codigo in codigos:
            texto_codigo = codigo.data.decode('utf-8')
            
            (x, y, w, h) = codigo.rect
            x_real, y_real = x + roi_x, y + roi_y
            
            cv2.rectangle(frame, (x_real, y_real), (x_real + w, y_real + h), (0, 255, 0), 2)

            # Lógica de las 5 lecturas
            if texto_codigo == codigo_actual:
                lecturas_consecutivas += 1
            else:
                codigo_actual = texto_codigo
                lecturas_consecutivas = 1
                
            cv2.putText(frame, f"Confirmando: {lecturas_consecutivas}/5", 
                        (x_real, y_real - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

            if lecturas_consecutivas >= lecturas_necesarias:
                codigo_confirmado = texto_codigo
                break

        # --- AQUI ESTA LA MAGIA DEL BUCLE CONTINUO ---
        if codigo_confirmado is not None:
            # 1. Dibujar la pantalla de éxito
            overlay = frame.copy()
            cv2.rectangle(overlay, (0, 0), (width, height), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

            cv2.putText(frame, "ESCANEO EXITOSO", (50, height // 2 - 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
            cv2.putText(frame, f"CODIGO: {codigo_confirmado}", (50, height // 2 + 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
            
            # Mostrar la pantalla de éxito
            cv2.imshow("Lector de Codigo de Barras", frame)
            
            # 2. Guardar el código y avisar por consola
            codigos_guardados.append(codigo_confirmado)
            print(f"Registrado: {codigo_confirmado}", flush=True)
            if on_codigo_scanned:
                try:
                    on_codigo_scanned(codigo_confirmado)
                except Exception:
                    pass

            # 3. Pausar la ejecución durante 2 segundos (2000 milisegundos)
            # Durante este tiempo el usuario puede retirar el producto
            cv2.waitKey(2000)

            # 4. REINICIAR los contadores para el siguiente producto
            codigo_actual = None
            lecturas_consecutivas = 0
            
            # Usamos 'continue' para saltar el final del ciclo y volver a leer la cámara inmediatamente
            continue

        # Mostrar la imagen en vivo normal
        cv2.imshow("Lector de Codigo de Barras", frame)

        # Salir con 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()
    
    # Devolver la lista completa de códigos escaneados
    return codigos_guardados

# === EJECUCIÓN ===
if __name__ == "__main__":
    import sys
    cam_arg = 1
    if len(sys.argv) > 1:
        try:
            cam_arg = int(sys.argv[1])
        except ValueError:
            pass
    lista_final = escaneo_continuo(camera_index=cam_arg)
    
    print("\n--- RESUMEN DE SESIÓN ---")
    if lista_final:
        print(f"Total de productos escaneados: {len(lista_final)}")
        print("Códigos guardados:")
        for idx, cod in enumerate(lista_final, 1):
            print(f"{idx}. {cod}")
    else:
        print("No se escaneó ningún código en esta sesión.")