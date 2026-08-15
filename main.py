import json
import os
import webbrowser

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

try:
    from kivy.app import App
    from kivy.clock import Clock
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.button import Button
    from kivy.uix.label import Label
    from kivy.uix.scrollview import ScrollView
    from kivy.uix.spinner import Spinner
    from kivy.uix.textinput import TextInput
    from kivy.uix.popup import Popup
    from kivy.uix.gridlayout import GridLayout
except ImportError:  # pragma: no cover
    App = object
    Clock = None
    BoxLayout = object
    Button = object
    Label = object
    ScrollView = object
    Spinner = object
    TextInput = object
    Popup = object
    GridLayout = object

import repartidor
import android_services

CONFIG_FILE = 'webServerApiSettings.json'

_MODO_TRAVELMODE = {'A pie': 'pie', 'Coche': 'coche', 'Moto': 'moto'}
_PRIORIDAD_VALS = list(repartidor.PRIORITY_ORDER)
_SELECT_PAQUETERIA = 'Seleccionar paquetería'
_SELECT_NOTIFICACION = 'Seleccionar notificación'


def _project_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _config_path():
    return os.path.join(_project_dir(), CONFIG_FILE)


def _hora_actual():
    """Devuelve la hora local actual (0-23) usando ``datetime.now().hour``."""
    from datetime import datetime
    return datetime.now().hour


class RepartidorApp(App if App is not object else object):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.lista_paradas = []
        self.api_key = repartidor.API_KEY or self._cargar_api_key_legacy()
        self.lbl_estado = None
        self.btn_ruta = None
        self.lista_widget = None
        self.spinner_modo = None
        self.spinner_prioridad = None
        self.spinner_paqueteria = None
        self.spinner_notificacion = None
        self.txt_busqueda = None
        self._ubicacion_actual = None
        self._paqueteria = None
        self._notificacion = None
        self._clock_19 = None

    # ------------------------------------------------------------------
    # Legacy API key loader (compatible con el JSON existente)
    # ------------------------------------------------------------------
    def _cargar_api_key_legacy(self):
        config_path = _config_path()
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as handle:
                    data = json.load(handle)
                if isinstance(data, dict):
                    return str(data.get('googleMapsApiKey', '') or '')
            except (OSError, ValueError):
                pass
        return ''

    # ------------------------------------------------------------------
    # Build UI
    # ------------------------------------------------------------------
    def build(self):
        if not hasattr(self, 'user_data_dir') or not self.user_data_dir:
            self.user_data_dir = _project_dir()

        root = BoxLayout(orientation='vertical', padding=10, spacing=8)

        # ---- Estado / info ----
        self.lbl_estado = Label(
            text='App Repartidor\nElige cómo introducir una dirección.',
            halign='center',
            font_size='15sp',
            size_hint_y=None,
            height='60dp',
        )
        root.add_widget(self.lbl_estado)

        # ---- Botones entrada de parada ----
        fila_entrada = BoxLayout(size_hint_y=None, height='50dp', spacing=6)
        btn_camara = Button(
            text='📷 Cámara',
            background_color=(0.1, 0.6, 0.9, 1),
        )
        btn_camara.bind(on_press=self.escanear_camara)

        btn_micro = Button(
            text='🎙 Micrófono',
            background_color=(0.2, 0.7, 0.3, 1),
        )
        btn_micro.bind(on_press=self.dictar_microfono)

        btn_ubicacion = Button(
            text='⌖ Ubicación',
            background_color=(0.5, 0.3, 0.8, 1),
        )
        btn_ubicacion.bind(on_press=self.solicitar_ubicacion)

        fila_entrada.add_widget(btn_camara)
        fila_entrada.add_widget(btn_micro)
        fila_entrada.add_widget(btn_ubicacion)
        root.add_widget(fila_entrada)

        # ---- Búsqueda manual ----
        fila_buscar = BoxLayout(size_hint_y=None, height='44dp', spacing=6)
        self.txt_busqueda = TextInput(
            hint_text='Escribir dirección…',
            multiline=False,
            size_hint_x=0.75,
        )
        btn_buscar = Button(
            text='🔍 Buscar',
            size_hint_x=0.25,
            background_color=(0.8, 0.5, 0.1, 1),
        )
        btn_buscar.bind(on_press=self.buscar_manual)
        fila_buscar.add_widget(self.txt_busqueda)
        fila_buscar.add_widget(btn_buscar)
        root.add_widget(fila_buscar)

        # ---- Selección prioridad y modo transporte ----
        fila_opts = BoxLayout(size_hint_y=None, height='44dp', spacing=6)
        fila_opts.add_widget(Label(text='Prioridad:', size_hint_x=0.3, font_size='13sp'))
        self.spinner_prioridad = Spinner(
            text='media',
            values=_PRIORIDAD_VALS,
            size_hint_x=0.35,
            background_normal='',
            background_color=repartidor.PRIORITY_COLORS['media'],
        )
        self.spinner_prioridad.bind(text=self._on_prioridad_cambio)
        fila_opts.add_widget(self.spinner_prioridad)
        fila_opts.add_widget(Label(text='Modo:', size_hint_x=0.15, font_size='13sp'))
        self.spinner_modo = Spinner(
            text='Moto',
            values=['A pie', 'Coche', 'Moto'],
            size_hint_x=0.2,
        )
        self.spinner_modo.bind(text=self._on_modo_cambio)
        fila_opts.add_widget(self.spinner_modo)
        root.add_widget(fila_opts)

        fila_selectores = BoxLayout(size_hint_y=None, height='44dp', spacing=6)
        self.spinner_paqueteria = Spinner(
            text=_SELECT_PAQUETERIA,
            values=['Correos', 'SEUR', 'MRW', 'DHL', 'Otra'],
        )
        self.spinner_paqueteria.bind(text=self._on_paqueteria_cambio)
        self.spinner_notificacion = Spinner(
            text=_SELECT_NOTIFICACION,
            values=['Sin notificación', 'SMS', 'Correo', 'Llamada'],
        )
        self.spinner_notificacion.bind(text=self._on_notificacion_cambio)
        fila_selectores.add_widget(self.spinner_paqueteria)
        fila_selectores.add_widget(self.spinner_notificacion)
        root.add_widget(fila_selectores)

        # ---- Lista de paradas ----
        scroll = ScrollView(size_hint=(1, 1))
        self.lista_widget = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            spacing=4,
        )
        self.lista_widget.bind(minimum_height=self.lista_widget.setter('height'))
        scroll.add_widget(self.lista_widget)
        root.add_widget(scroll)

        # ---- Botón Ver Ruta ----
        self.btn_ruta = Button(
            text='🗺 VER RUTA EN MAPS',
            size_hint_y=None,
            height='56dp',
            disabled=True,
            background_color=(0.8, 0.1, 0.1, 1),
        )
        self.btn_ruta.bind(on_press=self.abrir_google_maps)
        root.add_widget(self.btn_ruta)

        # No se solicitan permisos al arrancar; cada función los pide al usarse.
        self._programar_reloj_19()

        return root

    # ------------------------------------------------------------------
    # Geolocalización
    # ------------------------------------------------------------------
    def solicitar_ubicacion(self, *_args):
        self._set_estado('Solicitando acceso a la ubicación…')
        if not android_services.is_android():
            self._actualizar_ubicacion_escritorio()
            return
        android_services.request_runtime_permissions(
            android_services.LOCATION_PERMISSIONS,
            self._on_permiso_ubicacion,
        )

    def _on_permiso_ubicacion(self, concedido, denegados):
        if not concedido and not android_services.has_location_permission(denegados):
            self._set_estado(
                'Permiso de ubicación denegado.\n'
                'Concédelo en Ajustes y pulsa "Ubicación" para poder optimizar.'
            )
            return
        if not android_services.is_location_enabled():
            self._set_estado(
                'La ubicación del dispositivo está desactivada.\n'
                'Actívala en Ajustes y vuelve a pulsar "Ubicación".'
            )
            return
        self._set_estado('Obteniendo ubicación actual…')
        android_services.get_current_location(
            self._on_ubicacion,
            self._set_estado,
        )

    def _actualizar_ubicacion_escritorio(self):
        loc = repartidor.obtener_ubicacion_actual()
        if loc:
            self._on_ubicacion(loc)
        else:
            self._set_estado('No se pudo obtener la ubicación en este equipo.')

    def _on_ubicacion(self, loc):
        if not isinstance(loc, dict) or not repartidor.coordenadas_validas(
            loc.get('lat'), loc.get('lng')
        ):
            self._ubicacion_actual = None
            self._set_estado(
                'No se recibió una ubicación válida. Comprueba que la ubicación '
                'esté activa y vuelve a intentarlo.'
            )
            return
        self._ubicacion_actual = loc
        self._set_estado(f'Ubicación: {loc["lat"]:.4f}, {loc["lng"]:.4f}')
        self._refrescar_lista()

    # ------------------------------------------------------------------
    # Reloj 19:00
    # ------------------------------------------------------------------
    def _programar_reloj_19(self):
        """Recalcula la ruta cada minuto para aplicar la regla de las 19:00."""
        if Clock:
            self._clock_19 = Clock.schedule_interval(self._verificar_hora_19, 60)

    def _verificar_hora_19(self, *_args):
        hora = _hora_actual()
        if hora >= 19 and self.lista_paradas:
            self._set_estado('🕖 Son las 19:00 – reordenando por prioridad…')
            self._refrescar_lista()

    # ------------------------------------------------------------------
    # Entrada de paradas
    # ------------------------------------------------------------------
    def escanear_camara(self, *_args):
        """Toma una foto, extrae la dirección con OCR y añade la parada."""
        if android_services.is_android():
            self._set_estado('Solicitando acceso a la cámara…')
            android_services.request_runtime_permissions(
                android_services.CAMERA_PERMISSIONS,
                self._on_permiso_camara,
            )
            return
        self._abrir_camara()

    def _on_permiso_camara(self, concedido, _denegados):
        if not concedido:
            self._set_estado(
                'Permiso de cámara denegado. Puedes escribir la dirección manualmente.'
            )
            return
        self._abrir_camara()

    def _abrir_camara(self):
        self._set_estado('Abriendo cámara…')
        filepath = os.path.join(self.user_data_dir, 'temp_scan.jpg')
        self._eliminar_temporal(filepath)
        android_services.capture_photo(
            filepath,
            self._procesar_foto,
            self._set_estado,
        )

    def _procesar_foto(self, filepath):
        filepath = filepath or os.path.join(self.user_data_dir, 'temp_scan.jpg')
        if not os.path.isfile(filepath):
            self._set_estado('No se capturó ninguna imagen.')
            return
        self._set_estado('Procesando imagen…')
        if android_services.is_android():
            android_services.recognize_image_text(
                filepath,
                lambda texto: self._procesar_texto_ocr(texto, filepath),
                lambda error: self._error_captura(error, filepath),
            )
            return
        direccion, cp = repartidor.procesar_imagen(filepath)
        self._usar_direccion_ocr(direccion, cp)
        self._eliminar_temporal(filepath)

    def _procesar_texto_ocr(self, texto, filepath):
        direccion, cp = repartidor.extraer_direccion_texto_ocr(texto)
        self._usar_direccion_ocr(direccion, cp)
        self._eliminar_temporal(filepath)

    def _usar_direccion_ocr(self, direccion, cp):
        if direccion and cp:
            self._geocodificar_y_añadir(f'{direccion}, {cp}')
        elif direccion:
            self._geocodificar_y_añadir(direccion)
        else:
            self._set_estado('No se detectó dirección en la imagen.')

    def _error_captura(self, error, filepath):
        self._eliminar_temporal(filepath)
        self._set_estado(error)

    def dictar_microfono(self, *_args):
        """Dicta una dirección por voz y añade la parada."""
        if android_services.is_android():
            self._set_estado('Solicitando acceso al micrófono…')
            android_services.request_runtime_permissions(
                android_services.MICROPHONE_PERMISSIONS,
                self._on_permiso_microfono,
            )
            return
        self._set_estado('Escuchando micrófono…')
        texto = repartidor.dictar_direccion()
        if texto:
            self._geocodificar_y_añadir(texto)
        else:
            self._set_estado(
                'No se captó voz.\n'
                'Asegúrate de tener micrófono y SpeechRecognition instalado.'
            )

    def _on_permiso_microfono(self, concedido, _denegados):
        if not concedido:
            self._set_estado(
                'Permiso de micrófono denegado. Puedes escribir la dirección manualmente.'
            )
            return
        self._set_estado('Di ahora la dirección completa…')
        android_services.start_speech_recognition(
            self._geocodificar_y_añadir,
            self._set_estado,
        )

    def buscar_manual(self, *_args):
        """Geocodifica la dirección escrita manualmente."""
        texto = (self.txt_busqueda.text or '').strip() if self.txt_busqueda else ''
        if not texto:
            self._set_estado('Escribe una dirección primero.')
            return
        self._geocodificar_y_añadir(texto)
        if self.txt_busqueda:
            self.txt_busqueda.text = ''

    # ------------------------------------------------------------------
    # Geocodificación y gestión de paradas
    # ------------------------------------------------------------------
    def _geocodificar_y_añadir(self, texto):
        self._set_estado(f'Buscando: {texto}…')
        parada = repartidor.buscar_direccion_texto(texto)
        if parada is None:
            self._set_estado(
                'No se obtuvieron coordenadas para esa dirección. Comprueba la '
                'dirección, la conexión y la API key antes de añadirla.'
            )
            return
        prioridad = self.spinner_prioridad.text if self.spinner_prioridad else 'media'
        repartidor.asignar_prioridad(parada, prioridad)
        parada['paqueteria'] = self._paqueteria
        parada['notificacion'] = self._notificacion
        self.lista_paradas.append(parada)
        self._set_estado(f'Parada añadida: {parada.get("address", texto)}')
        self._refrescar_lista()

    def _refrescar_lista(self):
        if self.lista_widget is None:
            return
        self.lista_widget.clear_widgets()

        modo = _MODO_TRAVELMODE.get(self.spinner_modo.text if self.spinner_modo else 'Moto', 'moto')
        loc = self._ubicacion_actual or {}
        origen_lat = loc.get('lat')
        origen_lng = loc.get('lng')
        hora = _hora_actual()

        paradas_ord = repartidor.priorizar_paradas(
            self.lista_paradas, modo=modo,
            hora_actual=hora,
            origen_lat=origen_lat, origen_lng=origen_lng,
        )

        for idx, parada in enumerate(paradas_ord):
            fila = BoxLayout(size_hint_y=None, height='44dp', spacing=4)
            color = repartidor.PRIORITY_COLORS.get(
                parada.get('prioridad', 'media'),
                repartidor.PRIORITY_COLORS['media'],
            )
            lbl = Label(
                text=f"[{parada.get('prioridad','?')}] {parada.get('address','Sin dirección')}",
                halign='left',
                font_size='12sp',
                size_hint_x=0.8,
                text_size=(None, None),
                color=color,
            )
            btn_del = Button(
                text='✕',
                size_hint_x=0.2,
                background_normal='',
                background_color=color,
            )
            real_idx = self.lista_paradas.index(parada) if parada in self.lista_paradas else -1
            btn_del.bind(on_press=lambda _btn, i=real_idx: self._eliminar_parada(i))
            fila.add_widget(lbl)
            fila.add_widget(btn_del)
            self.lista_widget.add_widget(fila)

        if self.btn_ruta is not None:
            self.btn_ruta.disabled = not bool(self.lista_paradas)

    def _eliminar_parada(self, indice):
        repartidor.eliminar_parada(self.lista_paradas, indice)
        self._refrescar_lista()

    def _on_modo_cambio(self, *_args):
        self._refrescar_lista()

    def _on_prioridad_cambio(self, _spinner, prioridad):
        color = repartidor.PRIORITY_COLORS.get(
            prioridad, repartidor.PRIORITY_COLORS['media']
        )
        if self.spinner_prioridad is not None:
            self.spinner_prioridad.background_color = color

    def _on_paqueteria_cambio(self, spinner, valor):
        if valor == _SELECT_PAQUETERIA:
            return
        self._paqueteria = valor
        spinner.text = _SELECT_PAQUETERIA
        self._set_estado(f'Paquetería seleccionada: {valor}')

    def _on_notificacion_cambio(self, spinner, valor):
        if valor == _SELECT_NOTIFICACION:
            return
        self._notificacion = valor
        spinner.text = _SELECT_NOTIFICACION
        self._set_estado(f'Notificación seleccionada: {valor}')

    # ------------------------------------------------------------------
    # Abrir Maps
    # ------------------------------------------------------------------
    def abrir_google_maps(self, *_args):
        if not self.lista_paradas:
            self._set_estado('Añade al menos una dirección antes de crear la ruta.')
            return
        if android_services.is_android() and not android_services.is_location_enabled():
            self._set_estado(
                'La ubicación del dispositivo está desactivada. Actívala en '
                'Ajustes, pulsa "Ubicación" y vuelve a abrir la ruta.'
            )
            return
        modo = _MODO_TRAVELMODE.get(self.spinner_modo.text if self.spinner_modo else 'Moto', 'moto')
        loc = self._ubicacion_actual or {}
        url = repartidor.generar_ruta_maps(
            self.lista_paradas,
            modo=modo,
            hora_actual=_hora_actual(),
            origen_lat=loc.get('lat'),
            origen_lng=loc.get('lng'),
        )
        if url.startswith('http'):
            webbrowser.open(url)
        else:
            self._set_estado(url)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _set_estado(self, texto):
        if self.lbl_estado is not None:
            self.lbl_estado.text = str(texto)

    @staticmethod
    def _eliminar_temporal(filepath):
        try:
            if os.path.isfile(filepath):
                os.remove(filepath)
        except OSError:
            pass


if __name__ == '__main__':
    app = RepartidorApp()
    if hasattr(app, 'run'):
        app.run()
