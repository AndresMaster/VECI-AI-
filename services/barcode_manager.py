import threading
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Callable, List, Optional
import cv2
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
    def __init__(self, debounce_seconds: float = 1.2):
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
    Implementación 1 (Fase Pruebas):
    Captura continua de fotogramas mediante OpenCV y decodificación de códigos
    en segundo plano usando pyzbar.
    """
    def __init__(
        self,
        camera_index: int = 0,
        fps_target: int = 20,
        debounce_seconds: float = 1.2,
        frame_preview_callback: Optional[Callable[[any], None]] = None
    ):
        super().__init__(debounce_seconds=debounce_seconds)
        self.camera_index = camera_index
        self.frame_delay = 1.0 / fps_target
        self.frame_preview_callback = frame_preview_callback
        
        self._cap: Optional[cv2.VideoCapture] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._is_running = False

    def start(self) -> bool:
        if self._is_running:
            return True

        try:
            self._cap = cv2.VideoCapture(self.camera_index)
            if not self._cap.isOpened():
                print(f"[CameraScanner] No se pudo abrir la cámara index {self.camera_index}")
                return False

            self._stop_event.clear()
            self._thread = threading.Thread(target=self._capture_loop, daemon=True, name="CameraBarcodeThread")
            self._thread.start()
            self._is_running = True
            print("[CameraScanner] Escáner por cámara iniciado correctamente.")
            return True
        except Exception as ex:
            print(f"[CameraScanner] Excepción al iniciar cámara: {ex}")
            self.stop()
            return False

    def _capture_loop(self) -> None:
        while not self._stop_event.is_set():
            if self._cap is None or not self._cap.isOpened():
                break

            ret, frame = self._cap.read()
            if not ret or frame is None:
                time.sleep(self.frame_delay)
                continue

            # Decodificación de códigos de barras (EAN-13, CODE-128, QR, etc.)
            barcodes = pyzbar.decode(frame)
            for barcode in barcodes:
                try:
                    code_data = barcode.data.decode("utf-8")
                    self._emit_barcode(code_data)
                except Exception:
                    pass

            # Si la UI requiere previsualización de fotogramas
            if self.frame_preview_callback:
                try:
                    self.frame_preview_callback(frame)
                except Exception:
                    pass

            time.sleep(self.frame_delay)

    def stop(self) -> None:
        if not self._is_running:
            return

        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

        if self._cap and self._cap.isOpened():
            self._cap.release()
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


class BarcodeManager:
    """
    Manager / Fachada Unificada para gestión agnóstica de hardware de códigos de barras.
    Permite alternar entre la cámara web (fase pruebas) y el escáner USB (producción),
    notificando a los observadores registrados mediante on_barcode_scanned.
    """
    def __init__(
        self,
        mode: ScannerMode = ScannerMode.KEYBOARD_WEDGE,
        camera_index: int = 0
    ):
        self._mode = mode
        self._listeners: List[Callable[[str], None]] = []

        # Instancias de los scanners
        self.camera_scanner = CameraBarcodeScanner(camera_index=camera_index)
        self.wedge_scanner = KeyboardWedgeBarcodeScanner()

        # Enrutamiento de señales hacia el dispatcher central
        self.camera_scanner.set_callback(self._dispatch_barcode)
        self.wedge_scanner.set_callback(self._dispatch_barcode)

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

    def is_running(self) -> bool:
        return self.camera_scanner.is_running() or self.wedge_scanner.is_running()

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
