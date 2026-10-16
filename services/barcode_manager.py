import threading
import time
import base64
import os
import sys
import subprocess
from abc import ABC, abstractmethod
from enum import Enum
from typing import Callable, List, Optional, Union
import cv2
import numpy as np
from pyzbar import pyzbar

class ScannerMode(str, Enum):
    CAMERA = "CAMERA"               # Modo pruebas: Cámara web con OpenCV + pyzbar
    KEYBOARD_WEDGE = "KEYBOARD"     # Modo producción: Escáner USB emulando teclado
    BOTH = "BOTH"                   # Ambos activos simultáneamente
    DISABLED = "DISABLED"           # Desactivado


class BaseBarcodeScanner(ABC):
    """
    Clase base abstracta para lectores de código de barras.
    Garantiza el desacoplamiento de la fuente de captura respecto a la lógica de negocio.
    """
    def __init__(self, debounce_seconds: float = 2.0):
        self._callback: Optional[Callable[[str], None]] = None
        self._last_barcode: Optional[str] = None
        self._last_scan_time: float = 0.0
        self.debounce_seconds = debounce_seconds

    def set_callback(self, callback: Callable[[str], None]) -> None:
        """Asigna la función callback que recibirá el código escaneado."""
        self._callback = callback

    def _emit_barcode(self, raw_code: str) -> None:
        """
        Emite la señal de código detectado aplicando debounce temporal
        para evitar lecturas repetidas no deseadas del mismo código.
        """
        code = raw_code.strip()
        if not code:
            return

        now = time.time()
        # Filtro de rebote si es el mismo código leído en menos de debounce_seconds
        if code == self._last_barcode and (now - self._last_scan_time) < self.debounce_seconds:
            return

        self._last_barcode = code
        self._last_scan_time = now

        if self._callback:
            try:
                self._callback(code)
            except Exception as e:
                print(f"[BarcodeScanner Error] Error en callback de código: {e}")

    @abstractmethod
    def start(self) -> bool:
        """Inicia el servicio de captura."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Detiene el servicio y libera recursos."""
        pass

    @abstractmethod
    def is_running(self) -> bool:
        """Indica si el lector está actualmente en ejecución."""
        pass


class CameraBarcodeScanner(BaseBarcodeScanner):
    """
    Lector de códigos de barras mediante cámara web basado en el algoritmo de LectorBarr.py:
    - Resolución optimizada 640x480.
    - Región de interés central (ROI de 400x200) para máxima velocidad, nitidez y aislamiento de ruido.
    - Filtro CLAHE (clipLimit=2.0, tileGridSize=(8, 8)) + fallback en escala de grises.
    - Técnica de verificación estricta: Requiere 5 lecturas consecutivas idénticas antes de emitir.
    - Pantalla de éxito semi-transparente ("ESCANEO EXITOSO") con pausa de 2 segundos.
    - Transmisión en tiempo real a la interfaz mediante Base64 Data URI.
    """
    def __init__(
        self,
        camera_index: int = 1,
        fps_target: int = 25,
        debounce_seconds: float = 2.0,
        samples_required: int = 5,
        frame_preview_callback: Optional[Callable[[str], None]] = None,
        verification_callback: Optional[Callable[[str, int, int], None]] = None
    ):
        super().__init__(debounce_seconds=debounce_seconds)
        self.camera_index = camera_index
        self.frame_delay = 1.0 / fps_target
        self.samples_required = samples_required
        self.frame_preview_callback = frame_preview_callback
        self.verification_callback = verification_callback
        
        self._cap: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._is_running = False

        # Estado de verificación idéntico a LectorBarr.py
        self._candidate_code: Optional[str] = None
        self._candidate_samples: int = 0
        self._last_sample_time: float = 0.0
        self._last_preview_time: float = 0.0
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

    def start(self) -> bool:
        if self._is_running:
            return True

        try:
            print(f"[CameraScanner] Iniciando captura de video en cámara index {self.camera_index} (LectorBarr)...")
            self._cap = cv2.VideoCapture(self.camera_index)
            if not self._cap.isOpened():
                self._cap = cv2.VideoCapture(self.camera_index, cv2.CAP_AVFOUNDATION)

            if not self._cap.isOpened():
                print(f"[CameraScanner] Error: No se pudo acceder a la cámara index {self.camera_index}.")
                return False

            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            # Breve calentamiento de sensor
            for _ in range(5):
                ret, test_frame = self._cap.read()
                if ret and test_frame is not None:
                    break
                time.sleep(0.08)

            self._stop_event.clear()
            self._candidate_code = None
            self._candidate_samples = 0
            self._last_sample_time = 0.0

            self._thread = threading.Thread(target=self._capture_loop, daemon=True, name="CameraBarcodeThread")
            self._thread.start()
            self._is_running = True
            print(f"[CameraScanner] Escáner por cámara iniciado exitosamente (Índice activo: {self.camera_index}).")
            return True
        except Exception as ex:
            print(f"[CameraScanner] Excepción al iniciar cámara: {ex}")
            self.stop()
            return False

    def _reopen_capture(self) -> None:
        """Reconecta el dispositivo de cámara si el flujo de video se interrumpe."""
        try:
            if self._cap:
                try:
                    self._cap.release()
                except Exception:
                    pass
            time.sleep(0.3)
            self._cap = cv2.VideoCapture(self.camera_index)
            if not self._cap.isOpened():
                self._cap = cv2.VideoCapture(self.camera_index, cv2.CAP_AVFOUNDATION)
            if self._cap and self._cap.isOpened():
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                print(f"[CameraScanner] Cámara reconectada exitosamente en índice {self.camera_index}.")
        except Exception as ex:
            print(f"[CameraScanner] Error al reconectar cámara: {ex}")

    def _capture_loop(self) -> None:
        consecutive_failures = 0
        roi_w, roi_h = 400, 200

        try:
            while not self._stop_event.is_set():
                if self._cap is None or not self._cap.isOpened():
                    time.sleep(self.frame_delay)
                    continue

                try:
                    ret, frame = self._cap.read()
                except Exception:
                    ret, frame = False, None

                if not ret or frame is None:
                    consecutive_failures += 1
                    if consecutive_failures >= 15:
                        print(f"[CameraScanner] Flujo pausado o desconectado en cámara {self.camera_index}. Reconectando...")
                        self._reopen_capture()
                        consecutive_failures = 0
                    time.sleep(self.frame_delay)
                    continue

                consecutive_failures = 0
                now = time.time()
                h, w = frame.shape[:2]

                roi_x = max(0, (w - roi_w) // 2)
                roi_y = max(0, (h - roi_h) // 2)

                codigo_confirmado = None

                # 1. Dibujar el recuadro guía idéntico a LectorBarr.py
                cv2.rectangle(frame, (roi_x, roi_y), (roi_x + roi_w, roi_y + roi_h), (255, 0, 0), 2)
                cv2.putText(
                    frame,
                    "Ubica el codigo aqui",
                    (roi_x, roi_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 0, 0),
                    2
                )

                # 2. Extracción y análisis exclusivo de la ROI (Algoritmo LectorBarr)
                roi_frame = frame[roi_y:roi_y + roi_h, roi_x:roi_x + roi_w]
                codigos = []
                if roi_frame.size > 0:
                    gray = cv2.cvtColor(roi_frame, cv2.COLOR_BGR2GRAY)
                    procesado_clahe = self.clahe.apply(gray)
                    codigos = pyzbar.decode(procesado_clahe)
                    if not codigos:
                        codigos = pyzbar.decode(gray)

                    for codigo in codigos:
                        try:
                            texto_codigo = codigo.data.decode('utf-8').strip()
                            if not texto_codigo:
                                continue

                            (x, y, bw, bh) = codigo.rect
                            x_real, y_real = x + roi_x, y + roi_y

                            cv2.rectangle(frame, (x_real, y_real), (x_real + bw, y_real + bh), (0, 255, 0), 2)

                            # Lógica de las 5 lecturas consecutivas idéntica a LectorBarr.py
                            if texto_codigo == self._candidate_code:
                                self._candidate_samples += 1
                            else:
                                self._candidate_code = texto_codigo
                                self._candidate_samples = 1

                            self._last_sample_time = now

                            if self.verification_callback:
                                try:
                                    self.verification_callback(texto_codigo, self._candidate_samples, self.samples_required)
                                except Exception:
                                    pass

                            cv2.putText(
                                frame,
                                f"Confirmando: {self._candidate_samples}/{self.samples_required}",
                                (x_real, y_real - 10),
                                cv2.FONT_HERSHEY_SIMPLEX,
                                0.6,
                                (0, 255, 255),
                                2
                            )

                            if self._candidate_samples >= self.samples_required:
                                codigo_confirmado = texto_codigo
                                break
                        except Exception:
                            pass

                # Reset de contador si no se detecta código por más de 1.5s
                if not codigos and (now - self._last_sample_time) > 1.5:
                    if self._candidate_code is not None or self._candidate_samples > 0:
                        self._candidate_code = None
                        self._candidate_samples = 0
                        if self.verification_callback:
                            try:
                                self.verification_callback("", 0, self.samples_required)
                            except Exception:
                                pass

                # 3. Pantalla de éxito y emisión (Algoritmo LectorBarr)
                if codigo_confirmado is not None:
                    overlay = frame.copy()
                    cv2.rectangle(overlay, (0, 0), (w, h), (0, 0, 0), -1)
                    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)

                    cv2.putText(frame, "ESCANEO EXITOSO", (50, h // 2 - 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
                    cv2.putText(frame, f"CODIGO: {codigo_confirmado}", (50, h // 2 + 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)

                    # Emitir preview del éxito a la UI
                    if self.frame_preview_callback:
                        try:
                            preview_frame = cv2.resize(frame, (440, 280))
                            _, buffer = cv2.imencode('.jpg', preview_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                            b64_str = base64.b64encode(buffer.tobytes()).decode('ascii')
                            self.frame_preview_callback(f"data:image/jpeg;base64,{b64_str}")
                        except Exception:
                            pass

                    # Guardar y avisar por consola / emitir al sistema
                    print(f"[CameraScanner] Registrado: {codigo_confirmado}")
                    self._emit_barcode(codigo_confirmado)

                    # Pausar la ejecución durante 2 segundos (permitiendo retirar el producto)
                    for _ in range(20):
                        if self._stop_event.is_set():
                            break
                        time.sleep(0.1)

                    self._candidate_code = None
                    self._candidate_samples = 0
                    self._last_sample_time = 0.0
                    continue

                # 4. Transmisión del frame regular hacia la interfaz Flet (~15 FPS fluidos con Base64 Data URI)
                if self.frame_preview_callback and (now - self._last_preview_time) >= 0.065:
                    try:
                        self._last_preview_time = now
                        preview_frame = cv2.resize(frame, (440, 280))
                        _, buffer = cv2.imencode('.jpg', preview_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                        b64_str = base64.b64encode(buffer.tobytes()).decode('ascii')
                        self.frame_preview_callback(f"data:image/jpeg;base64,{b64_str}")
                    except Exception:
                        pass

                time.sleep(self.frame_delay)
        except Exception as loop_fatal:
            print(f"[CameraScanner] Excepción en bucle de captura: {loop_fatal}")
        finally:
            self._is_running = False

    def stop(self) -> None:
        if not self._is_running and (self._cap is None or not self._cap.isOpened()):
            return

        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)

        if self._cap:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

        self._is_running = False
        print("[CameraScanner] Escáner por cámara detenido.")

    def is_running(self) -> bool:
        return self._is_running


class KeyboardWedgeBarcodeScanner(BaseBarcodeScanner):
    """
    Implementación 2 (Fase Producción):
    Lectura por escáner USB tipo 'Keyboard Wedge'.
    Los lectores físicos USB actúan como dispositivos de entrada rápida de teclado
    enviando una ráfaga veloz de caracteres seguida de una tecla 'Enter'.
    """
    def __init__(
        self,
        max_inter_char_ms: int = 100,
        min_barcode_length: int = 3,
        debounce_seconds: float = 1.0
    ):
        super().__init__(debounce_seconds=debounce_seconds)
        self.max_inter_char_ms = max_inter_char_ms
        self.min_barcode_length = min_barcode_length

        self._buffer: List[str] = []
        self._last_char_timestamp: float = 0.0
        self._lock = threading.Lock()
        self._active = False

    def start(self) -> bool:
        self._active = True
        self._reset_buffer()
        print("[KeyboardWedgeScanner] Escáner USB (Keyboard Wedge) activado.")
        return True

    def stop(self) -> None:
        self._active = False
        self._reset_buffer()
        print("[KeyboardWedgeScanner] Escáner USB desactivado.")

    def is_running(self) -> bool:
        return self._active

    def _reset_buffer(self) -> None:
        with self._lock:
            self._buffer.clear()
            self._last_char_timestamp = 0.0

    def process_key_event(self, key_name: str) -> bool:
        """
        Recibe eventos del teclado (por ejemplo desde page.on_keyboard_event en Flet).
        Retorna True si el evento fue consumido como parte de una lectura de código.
        """
        if not self._active:
            return False

        now = time.time() * 1000.0  # milisegundos

        with self._lock:
            # Si el intervalo entre pulsaciones es muy grande, reiniciar el buffer
            if self._buffer and (now - self._last_char_timestamp) > self.max_inter_char_ms:
                self._buffer.clear()

            # Detección del final de lectura del escáner (Enter / Intro)
            if key_name in ("Enter", "Return", "\r", "\n"):
                if len(self._buffer) >= self.min_barcode_length:
                    scanned_code = "".join(self._buffer)
                    self._buffer.clear()
                    self._last_char_timestamp = 0.0
                    self._emit_barcode(scanned_code)
                    return True
                self._buffer.clear()
                return False

            # Captura de caracteres imprimibles (alfanuméricos y guiones comunes en códigos)
            if len(key_name) == 1:
                self._buffer.append(key_name)
                self._last_char_timestamp = now
                return True

        return False

    def simulate_scan(self, simulated_code: str) -> None:
        """Permite inyectar un código programáticamente para pruebas unitarias o de UI."""
        self._emit_barcode(simulated_code)


class NativeLectorScanner(BaseBarcodeScanner):
    """
    Controlador para ejecutar LectorBarr.py como ventana nativa flotante de OpenCV.
    Permite abrir la ventana nativa directamente desde la interfaz y recibir los códigos
    escaneados por tubería estándar (stdout) en tiempo real.
    """
    def __init__(self, camera_index: int = 1):
        super().__init__(debounce_seconds=1.5)
        self.camera_index = camera_index
        self._process: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._is_running = False

    def start(self) -> bool:
        if self._is_running and self._process and self._process.poll() is None:
            return True

        script_path = os.path.join(os.getcwd(), "LectorBarr.py")
        if not os.path.exists(script_path):
            print(f"[NativeLector] Archivo no encontrado: {script_path}")
            return False

        try:
            self._process = subprocess.Popen(
                [sys.executable, script_path, str(self.camera_index)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            self._is_running = True
            self._thread = threading.Thread(target=self._read_stdout, daemon=True, name="NativeLectorReader")
            self._thread.start()
            print(f"[NativeLector] Ventana nativa de LectorBarr iniciada (PID: {self._process.pid}, Cámara: {self.camera_index})")
            return True
        except Exception as e:
            print(f"[NativeLector] Error al iniciar LectorBarr.py: {e}")
            self._is_running = False
            return False

    def _read_stdout(self) -> None:
        try:
            if not self._process or not self._process.stdout:
                return
            for line in self._process.stdout:
                line_str = line.strip()
                if "Registrado: " in line_str:
                    code = line_str.split("Registrado: ")[-1].strip()
                    if code:
                        print(f"[NativeLector] Código recibido desde LectorBarr.py: {code}")
                        self._emit_barcode(code)
        except Exception as ex:
            print(f"[NativeLector] Excepción en lectura de salida: {ex}")
        finally:
            self._is_running = False

    def stop(self) -> None:
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=1.0)
            except Exception:
                try:
                    self._process.kill()
                except Exception:
                    pass
            self._process = None
        self._is_running = False
        print("[NativeLector] Ventana nativa de LectorBarr finalizada.")

    def is_running(self) -> bool:
        return self._is_running and (self._process is not None) and (self._process.poll() is None)


class BarcodeManager:
    """
    Manager / Fachada Unificada para gestión agnóstica de hardware de códigos de barras.
    Permite alternar entre la cámara web con verificación multicapa y el escáner USB,
    notificando a los observadores registrados mediante on_barcode_scanned.
    """
    def __init__(
        self,
        mode: ScannerMode = ScannerMode.KEYBOARD_WEDGE,
        camera_index: int = 1
    ):
        self._mode = mode
        self._listeners: List[Callable[[str], None]] = []

        # Instancias de los scanners (por defecto cámara index 1)
        self.camera_scanner = CameraBarcodeScanner(camera_index=camera_index)
        self.wedge_scanner = KeyboardWedgeBarcodeScanner()
        self.native_scanner = NativeLectorScanner(camera_index=camera_index)

        # Enrutamiento de señales hacia el dispatcher central
        self.camera_scanner.set_callback(self._dispatch_barcode)
        self.wedge_scanner.set_callback(self._dispatch_barcode)
        self.native_scanner.set_callback(self._dispatch_barcode)

    def subscribe(self, listener: Callable[[str], None]) -> None:
        """Registra un observador que responderá al evento on_barcode_scanned(code)."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def unsubscribe(self, listener: Callable[[str], None]) -> None:
        """Remueve un observador."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    def set_mode(self, mode: ScannerMode) -> None:
        """Cambia el modo activo de captura."""
        if self._mode == mode:
            return

        was_running = self.is_running()
        if was_running:
            self.stop()

        self._mode = mode

        if was_running:
            self.start()

    def set_camera_index(self, camera_index: int) -> None:
        """Permite cambiar el índice de la cámara (ej. 1 por defecto, o 0 para integrada)."""
        was_running = self.camera_scanner.is_running()
        if was_running:
            self.camera_scanner.stop()
            time.sleep(0.3)  # Da tiempo a macOS AVFoundation para desvincular y liberar el recurso
        self.camera_scanner.camera_index = camera_index
        self.native_scanner.camera_index = camera_index
        if was_running:
            self.camera_scanner.start()

    def start_native_window(self) -> bool:
        """Inicia la ventana nativa de OpenCV (LectorBarr.py)."""
        if self.camera_scanner.is_running():
            self.camera_scanner.stop()
            time.sleep(0.3)
        self.native_scanner.camera_index = self.camera_index
        return self.native_scanner.start()

    def stop_native_window(self) -> None:
        """Detiene la ventana nativa de OpenCV si está activa."""
        if self.native_scanner.is_running():
            self.native_scanner.stop()

    def toggle_native_window(self) -> bool:
        """Inicia o detiene la ventana nativa de OpenCV (LectorBarr.py)."""
        if self.native_scanner.is_running():
            self.stop_native_window()
            if self._mode in (ScannerMode.CAMERA, ScannerMode.BOTH):
                time.sleep(0.3)
                self.camera_scanner.start()
            return False
        else:
            return self.start_native_window()

    def is_native_window_running(self) -> bool:
        return self.native_scanner.is_running()

    @property
    def camera_index(self) -> int:
        return self.camera_scanner.camera_index

    def set_preview_callback(self, callback: Optional[Callable[[str], None]]) -> None:
        """Asigna callback para recibir fotogramas (formato data:image/jpeg;base64) para previsualización."""
        self.camera_scanner.frame_preview_callback = callback

    def set_verification_callback(self, callback: Optional[Callable[[str, int, int], None]]) -> None:
        """Asigna callback para recibir el estado de verificación de muestras (código, actuales, requeridas)."""
        self.camera_scanner.verification_callback = callback

    @staticmethod
    def get_available_cameras(max_tested: int = 4) -> List[int]:
        """Detecta los índices de cámaras físicas conectadas al equipo."""
        available = []
        for i in range(max_tested):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append(i)
                cap.release()
        return available

    @property
    def mode(self) -> ScannerMode:
        return self._mode

    def start(self) -> bool:
        """Inicia el/los lectores de acuerdo al modo configurado."""
        success = True
        if self._mode in (ScannerMode.CAMERA, ScannerMode.BOTH):
            cam_ok = self.camera_scanner.start()
            success = success and cam_ok
        if self._mode in (ScannerMode.KEYBOARD_WEDGE, ScannerMode.BOTH):
            wedge_ok = self.wedge_scanner.start()
            success = success and wedge_ok
        return success

    def stop(self) -> None:
        """Detiene todos los lectores activos."""
        self.camera_scanner.stop()
        self.wedge_scanner.stop()
        self.native_scanner.stop()

    def is_running(self) -> bool:
        return self.camera_scanner.is_running() or self.wedge_scanner.is_running() or self.native_scanner.is_running()

    def handle_keyboard_event(self, key_name: str) -> bool:
        """Delega eventos de teclado al escáner USB si el modo lo admite."""
        if self._mode in (ScannerMode.KEYBOARD_WEDGE, ScannerMode.BOTH):
            return self.wedge_scanner.process_key_event(key_name)
        return False

    def scan_code(self, code: str) -> None:
        """Invocación directa de escaneo (para cajas de texto de entrada manual o tests)."""
        self._dispatch_barcode(code)

    def _dispatch_barcode(self, code: str) -> None:
        """
        Dispara la señal on_barcode_scanned(código) a todos los controladores suscritos.
        La lógica de negocio recibe esta señal de forma totalmente agnóstica del hardware.
        """
        for listener in list(self._listeners):
            try:
                listener(code)
            except Exception as e:
                print(f"[BarcodeManager] Error notificando al observador: {e}")
