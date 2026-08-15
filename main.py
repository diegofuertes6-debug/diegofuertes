"""Aplicación principal de Repartidor.

Este archivo está pensado para compilar con Buildozer y para seguir
funcionando si no se dispone de Kivy o de la configuración de API.
"""

import json
import os
import sys
import webbrowser

try:
    import requests
except Exception:  # pragma: no cover - entorno sin red / dependencias
    requests = None

try:
    from kivy.app import App
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.label import Label
    KIVY_AVAILABLE = True
except Exception:  # pragma: no cover - compilación o entorno sin Kivy
    App = object
    BoxLayout = object
    Button = object
    Label = object
    KIVY_AVAILABLE = False

CONFIG_FILE = "webServerApiSettings.json"


def project_dir():
    return os.path.dirname(os.path.abspath(__file__))


def config_path():
    return os.path.join(project_dir(), CONFIG_FILE)


def load_api_key():
    path = config_path()
    if not os.path.exists(path):
        return "TU_API_KEY_AQUI"

    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError, TypeError):
        return "TU_API_KEY_AQUI"

    if not isinstance(payload, dict):
        return "TU_API_KEY_AQUI"

    for key in ("googleMapsApiKey", "google_maps_api_key", "apiKey"):
        value = payload.get(key)
        if value:
            return str(value)
    return "TU_API_KEY_AQUI"


class RepartidorApp(App if KIVY_AVAILABLE else object):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.lista_paradas = []
        self.api_key = load_api_key()
        self.lbl = None
        self.btn_ruta = None
        self.user_data_dir = project_dir()

    def build(self):
        if not KIVY_AVAILABLE:
            return None

        layout = BoxLayout(orientation="vertical", padding=20, spacing=15)
        self.lbl = Label(
            text="App Repartidor v1.0\nListo para escanear",
            halign="center",
            font_size="18sp",
        )

        btn_foto = Button(
            text="CAPTURAR DIRECCIÓN",
            size_hint_y=None,
            height="80dp",
            background_color=(0.1, 0.6, 0.9, 1),
        )
        btn_foto.bind(on_press=self.tomar_foto)

        self.btn_ruta = Button(
            text="VER RUTA EN MAPS",
            size_hint_y=None,
            height="80dp",
            disabled=True,
        )
        self.btn_ruta.bind(on_press=self.abrir_google_maps)

        layout.add_widget(self.lbl)
        layout.add_widget(btn_foto)
        layout.add_widget(self.btn_ruta)
        return layout

    def tomar_foto(self, *args):
        if self.lbl is None:
            return

        filepath = os.path.join(self.user_data_dir, "temp.jpg")
        try:
            from plyer import camera
            camera.take_picture(filename=filepath, on_complete=self.procesar_ocr)
        except Exception as exc:  # pragma: no cover - depende del entorno
            self.lbl.text = f"Error de cámara: {exc}"

    def procesar_ocr(self, filepath):
        del filepath
        direccion = "Calle Ejemplo 123"
        cp = "28001"
        self.lbl.text = f"Buscando: {direccion}, {cp}"
        self.obtener_geo(direccion, cp)

    def obtener_geo(self, direccion, cp):
        if self.lbl is None:
            return

        if requests is None:
            self.lbl.text = "Error de conexión con Google"
            return

        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            "address": f"{direccion}, {cp}, España",
            "key": self.api_key,
        }

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            payload = response.json()
            if payload.get("status") == "OK":
                loc = payload["results"][0]["geometry"]["location"]
                self.lista_paradas.append(f"{loc['lat']},{loc['lng']}")
                self.btn_ruta.disabled = False
                self.lbl.text = (
                    f"Parada añadida:\n{payload['results'][0]['formatted_address']}"
                )
                return
        except Exception:
            pass

        self.lbl.text = "Error de conexión con Google"

    def abrir_google_maps(self, *args):
        if not self.lista_paradas:
            return

        destino = self.lista_paradas[-1]
        url = f"https://www.google.com/maps/dir/?api=1&destination={destino}"
        if len(self.lista_paradas) > 1:
            url += f"&waypoints={'|'.join(self.lista_paradas[:-1])}"
        try:
            webbrowser.open(url)
        except Exception:
            pass


if __name__ == "__main__":
    if not KIVY_AVAILABLE:
        print("Kivy no está disponible en este entorno. La app no se puede ejecutar aquí.")
        sys.exit(0)

    app = RepartidorApp()
    app.run()
