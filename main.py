import os
import threading
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
import auth

_MODO_TRAVELMODE = {'A pie': 'pie', 'Coche': 'coche', 'Moto': 'moto'}
_PRIORIDAD_VALS = list(repartidor.PRIORITY_ORDER)
_SELECT_CARTAS = 'Cartas'
STOP_ACTIONS = (
    ('texto', '🔍', 'Texto', 'Validar y añadir dirección escrita', 'buscar_manual'),
    ('voz', '🎙', 'Voz', 'Dictar, revisar y añadir dirección', 'dictar_microfono'),
    ('escaner', '📷', 'Escáner', 'Escanear, revisar y añadir dirección', 'escanear_camara'),
)
INTEGRATED_STOP_BUTTON_TEXT = '➕ AÑADIR PARADA\n📷 Escáner · 🔍 Lupa · 🎙 Micrófono'


def _project_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _hora_actual():
    """Devuelve los minutos totales desde medianoche usando ``datetime.now()``."""
    from datetime import datetime
    now = datetime.now()
    return now.hour * 60 + now.minute


class RepartidorApp(App if App is not object else object):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.lista_paradas = []
        self.api_key = repartidor.API_KEY
        self.lbl_estado = None
        self.btn_ruta = None
        self.btn_acciones_parada = None
        self.lista_widget = None
        self.spinner_modo = None
        self.spinner_prioridad = None
        self.spinner_paqueteria = None
        self.spinner_notificacion = None
        self.txt_busqueda = None
        self._ubicacion_actual = None
        self._paqueteria = repartidor.DEFAULT_PACKAGE
        self._notificacion = repartidor.DEFAULT_LETTER
        self._clock_19 = None
        self._popup_confirmacion = None
        self._popup_acciones_parada = None
        self._temp_scan_path = None
        self._camera_en_curso = False
        self._location_permission_requested = False
        self._location_permission_denied = False
        self._location_request_in_progress = False
        self._location_request_generation = 0
        self._location_cancel = None
        self._waiting_location_settings = False
        self._location_dialog_shown = False
        self._resume_location_after_pause = False
        self._open_map_when_located = False
        # Autenticación
        self._usuario_actual = None
        self._popup_auth = None

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

        self.txt_busqueda = TextInput(
            hint_text='Escribir dirección…',
            multiline=False,
            padding=(10, 18),
        )
        self.txt_busqueda.bind(on_text_validate=self.buscar_manual)

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
            text=repartidor.DEFAULT_PACKAGE,
            values=repartidor.PACKAGE_OPTIONS,
        )
        self.spinner_paqueteria.bind(text=self._on_paqueteria_cambio)
        self.spinner_notificacion = Spinner(
            text=_SELECT_CARTAS,
            values=repartidor.LETTER_OPTIONS,
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

        # ---- Botón integrado de alta de parada ----
        self.btn_acciones_parada = Button(
            text=INTEGRATED_STOP_BUTTON_TEXT,
            size_hint_y=None,
            height='72dp',
            font_size='16sp',
            background_normal='',
            background_color=(0.15, 0.45, 0.85, 1),
        )
        self.btn_acciones_parada.bind(on_press=self.mostrar_acciones_parada)
        root.add_widget(self.btn_acciones_parada)

        self._programar_reloj_19()
        if Clock:
            Clock.schedule_once(self._mostrar_login, 0.3)
        else:
            self._mostrar_login()

        return root

    # ------------------------------------------------------------------
    # Autenticación – login / registro / donación
    # ------------------------------------------------------------------
    def _mostrar_login(self, *_args):
        """Muestra el popup de inicio de sesión al arrancar la app."""
        if Popup is object:
            # Entorno sin Kivy (tests / escritorio sin display): arrancamos
            # directamente sin requerir autenticación.
            if Clock:
                Clock.schedule_once(self._solicitar_ubicacion_inicial, 0.2)
            else:
                self._solicitar_ubicacion_inicial()
            return

        contenido = BoxLayout(orientation='vertical', padding=14, spacing=10)
        contenido.add_widget(Label(
            text='🚚 App Repartidor\nInicia sesión para continuar',
            halign='center',
            font_size='16sp',
            size_hint_y=None,
            height='60dp',
        ))
        txt_user = TextInput(
            hint_text='Usuario',
            multiline=False,
            size_hint_y=None,
            height='48dp',
            padding=(10, 12),
        )
        txt_pass = TextInput(
            hint_text='Contraseña',
            password=True,
            multiline=False,
            size_hint_y=None,
            height='48dp',
            padding=(10, 12),
        )
        lbl_error = Label(
            text='',
            color=(1, 0.3, 0.3, 1),
            size_hint_y=None,
            height='36dp',
            halign='center',
        )
        contenido.add_widget(txt_user)
        contenido.add_widget(txt_pass)
        contenido.add_widget(lbl_error)

        btn_entrar = Button(
            text='Entrar',
            size_hint_y=None,
            height='48dp',
            background_color=(0.2, 0.6, 0.9, 1),
        )
        btn_registrar = Button(
            text='Crear cuenta nueva',
            size_hint_y=None,
            height='44dp',
            background_color=(0.2, 0.7, 0.3, 1),
        )
        contenido.add_widget(btn_entrar)
        contenido.add_widget(btn_registrar)

        popup = Popup(
            title='Iniciar sesión',
            content=contenido,
            size_hint=(0.9, None),
            height='420dp',
            auto_dismiss=False,
        )
        self._popup_auth = popup

        def _login(*_):
            usuario = txt_user.text.strip()
            contrasena = txt_pass.text
            if not usuario or not contrasena:
                lbl_error.text = 'Rellena usuario y contraseña.'
                return
            if auth.verify_user(self.user_data_dir, usuario, contrasena):
                self._usuario_actual = usuario
                popup.dismiss()
                self._popup_auth = None
                tipo = auth.get_account_type(self.user_data_dir, usuario)
                if tipo == auth.ACCOUNT_TRIAL:
                    self._set_estado(
                        f'Bienvenido, {usuario} 👋  '
                        f'(Versión prueba: máx. {auth.TRIAL_MAX_PARADAS} paradas)'
                    )
                else:
                    self._set_estado(f'Bienvenido, {usuario} 👋  (Versión completa ✅)')
                if Clock:
                    Clock.schedule_once(self._solicitar_ubicacion_inicial, 0.2)
                else:
                    self._solicitar_ubicacion_inicial()
            else:
                lbl_error.text = 'Usuario o contraseña incorrectos.'

        btn_entrar.bind(on_press=_login)
        txt_pass.bind(on_text_validate=_login)
        btn_registrar.bind(on_press=lambda *_: self._mostrar_registro(popup))
        popup.open()

    def _mostrar_registro(self, popup_login):
        """Cierra el login y abre el formulario de registro."""
        popup_login.dismiss()
        if Popup is object:
            return

        contenido = BoxLayout(orientation='vertical', padding=14, spacing=10)
        contenido.add_widget(Label(
            text='Crear cuenta nueva',
            halign='center',
            font_size='16sp',
            size_hint_y=None,
            height='44dp',
        ))
        txt_user = TextInput(
            hint_text='Nombre de usuario',
            multiline=False,
            size_hint_y=None,
            height='48dp',
            padding=(10, 12),
        )
        txt_pass = TextInput(
            hint_text='Contraseña',
            password=True,
            multiline=False,
            size_hint_y=None,
            height='48dp',
            padding=(10, 12),
        )
        txt_pass2 = TextInput(
            hint_text='Repite la contraseña',
            password=True,
            multiline=False,
            size_hint_y=None,
            height='48dp',
            padding=(10, 12),
        )
        lbl_error = Label(
            text='',
            color=(1, 0.3, 0.3, 1),
            size_hint_y=None,
            height='36dp',
            halign='center',
        )
        contenido.add_widget(txt_user)
        contenido.add_widget(txt_pass)
        contenido.add_widget(txt_pass2)
        contenido.add_widget(lbl_error)

        fila_btns = BoxLayout(size_hint_y=None, height='48dp', spacing=8)
        btn_volver = Button(text='← Volver', background_color=(0.5, 0.5, 0.5, 1))
        btn_crear = Button(text='Crear cuenta', background_color=(0.2, 0.7, 0.3, 1))
        fila_btns.add_widget(btn_volver)
        fila_btns.add_widget(btn_crear)
        contenido.add_widget(fila_btns)

        popup = Popup(
            title='Registro',
            content=contenido,
            size_hint=(0.9, None),
            height='480dp',
            auto_dismiss=False,
        )
        self._popup_auth = popup

        def _registrar(*_):
            usuario = txt_user.text.strip()
            contrasena = txt_pass.text
            contrasena2 = txt_pass2.text
            if not usuario or not contrasena:
                lbl_error.text = 'Rellena todos los campos.'
                return
            if contrasena != contrasena2:
                lbl_error.text = 'Las contraseñas no coinciden.'
                return
            try:
                ok = auth.register_user(self.user_data_dir, usuario, contrasena)
            except ValueError as exc:
                lbl_error.text = str(exc)
                return
            if not ok:
                lbl_error.text = 'Ese nombre de usuario ya existe.'
                return
            self._usuario_actual = usuario
            popup.dismiss()
            self._popup_auth = None
            self._set_estado(
                f'¡Cuenta creada! Bienvenido, {usuario} 👋  '
                f'(Versión prueba: máx. {auth.TRIAL_MAX_PARADAS} paradas)'
            )
            if Clock:
                Clock.schedule_once(self._solicitar_ubicacion_inicial, 0.2)
            else:
                self._solicitar_ubicacion_inicial()

        btn_crear.bind(on_press=_registrar)
        btn_volver.bind(on_press=lambda *_: self._reabrir_login(popup))
        popup.open()

    def _reabrir_login(self, popup_registro):
        """Cierra el registro y vuelve al login."""
        popup_registro.dismiss()
        self._mostrar_login()

    def _mostrar_donacion(self, *_args):
        """Muestra el popup de donación para desbloquear la versión completa."""
        if Popup is object:
            return

        contenido = BoxLayout(orientation='vertical', padding=14, spacing=10)
        contenido.add_widget(Label(
            text=(
                '🎁 Versión completa\n\n'
                'La versión de prueba está limitada a\n'
                f'{auth.TRIAL_MAX_PARADAS} paradas.\n\n'
                'Haz una donación para desbloquear\n'
                'la versión completa sin límites.'
            ),
            halign='center',
            font_size='14sp',
            size_hint_y=None,
            height='180dp',
        ))

        btn_donar = Button(
            text='☕ Donar y desbloquear',
            size_hint_y=None,
            height='52dp',
            background_color=(0.95, 0.6, 0.1, 1),
        )
        btn_cerrar = Button(
            text='Ahora no',
            size_hint_y=None,
            height='44dp',
            background_color=(0.45, 0.45, 0.45, 1),
        )
        contenido.add_widget(btn_donar)
        contenido.add_widget(btn_cerrar)

        popup = Popup(
            title='Desbloquear versión completa',
            content=contenido,
            size_hint=(0.88, None),
            height='400dp',
            auto_dismiss=False,
        )

        def _abrir_donacion(*_):
            if android_services.is_android():
                android_services.open_map_url(auth.DONATION_URL, self._set_estado)
            else:
                webbrowser.open(auth.DONATION_URL)
            # Tras donar el usuario puede pedir al desarrollador que active full
            popup.dismiss()
            self._set_estado(
                '¡Gracias! Una vez confirmada la donación tu cuenta será activada. '
                'Contacta con soporte si necesitas ayuda.'
            )

        btn_donar.bind(on_press=_abrir_donacion)
        btn_cerrar.bind(on_press=lambda *_: popup.dismiss())
        popup.open()

    # ------------------------------------------------------------------
    # Geolocalización
    # ------------------------------------------------------------------
    def _solicitar_ubicacion_inicial(self, *_args):
        self.solicitar_ubicacion(contexto_inicial=True)

    def solicitar_ubicacion(self, *_args, contexto_inicial=False):
        if self._location_request_in_progress:
            self._set_estado('Ya se está obteniendo la ubicación actual…')
            return
        if _args and not contexto_inicial:
            self._location_dialog_shown = False
        self._set_estado('Solicitando acceso a la ubicación…')
        if not android_services.is_android():
            self._actualizar_ubicacion_escritorio()
            return
        if android_services.location_permission_granted():
            self._location_permission_denied = False
            self._comprobar_proveedor_y_localizar(prompt_settings=True)
            return
        if self._location_permission_denied or self._location_permission_requested:
            self._open_map_when_located = False
            self._set_estado(
                'La ubicación no tiene permiso. Actívalo en Ajustes de la app '
                'para usar tu posición como depósito.'
            )
            return
        self._location_permission_requested = True
        self._set_estado(
            'Necesitamos tu ubicación para usar el punto actual como salida y '
            'regreso de la ruta. Android mostrará ahora el permiso.'
        )
        android_services.request_runtime_permissions(
            android_services.LOCATION_PERMISSIONS,
            self._on_permiso_ubicacion,
        )

    def _on_permiso_ubicacion(self, concedido, denegados):
        if not concedido and not android_services.has_location_permission(denegados):
            self._open_map_when_located = False
            self._location_permission_denied = True
            self._set_estado(
                'Permiso de ubicación denegado. No volveremos a solicitarlo '
                'automáticamente; puedes activarlo en Ajustes de la app.'
            )
            return
        self._location_permission_denied = False
        self._comprobar_proveedor_y_localizar(prompt_settings=True)

    def _comprobar_proveedor_y_localizar(self, prompt_settings):
        if not android_services.is_location_enabled():
            self._ubicacion_actual = None
            self._refrescar_lista()
            if prompt_settings and not self._location_dialog_shown:
                self._mostrar_dialogo_activar_ubicacion()
            else:
                self._set_estado(
                    'La ubicación del dispositivo está apagada. Actívala en '
                    'Ajustes; al volver reintentaremos obtener tu posición.'
                )
            return
        self._location_dialog_shown = False
        self._iniciar_localizacion()

    def _mostrar_dialogo_activar_ubicacion(self):
        self._location_dialog_shown = True
        mensaje = (
            'La ubicación del dispositivo está apagada. Debes activarla para '
            'usar tu posición actual como inicio y final de la ruta.'
        )
        self._set_estado(mensaje)
        if Popup is object:
            self._abrir_ajustes_ubicacion()
            return
        contenido = BoxLayout(orientation='vertical', padding=12, spacing=10)
        contenido.add_widget(Label(text=mensaje, halign='center'))
        acciones = BoxLayout(size_hint_y=None, height='52dp', spacing=10)
        cancelar = Button(text='Ahora no')
        abrir = Button(text='Abrir ajustes', background_color=(0.2, 0.7, 0.3, 1))
        acciones.add_widget(cancelar)
        acciones.add_widget(abrir)
        contenido.add_widget(acciones)
        popup = Popup(
            title='Activar ubicación',
            content=contenido,
            size_hint=(0.92, None),
            height='260dp',
            auto_dismiss=False,
        )
        cancelar.bind(on_press=lambda *_args: popup.dismiss())
        abrir.bind(
            on_press=lambda *_args: self._confirmar_ajustes_ubicacion(popup)
        )
        popup.open()

    def _confirmar_ajustes_ubicacion(self, popup):
        popup.dismiss()
        self._abrir_ajustes_ubicacion()

    def _abrir_ajustes_ubicacion(self):
        self._waiting_location_settings = android_services.open_location_settings(
            self._set_estado
        )
        if self._waiting_location_settings:
            self._set_estado(
                'Activa la ubicación en el panel del sistema y vuelve a la app.'
            )

    def _iniciar_localizacion(self):
        if self._location_request_in_progress:
            return
        self._location_request_generation += 1
        generation = self._location_request_generation
        self._location_request_in_progress = True
        self._set_estado('Obteniendo ubicación actual…')
        self._location_cancel = android_services.get_current_location(
            lambda loc: self._on_ubicacion_generacion(generation, loc),
            lambda error: self._on_error_ubicacion(generation, error),
        )

    def _on_ubicacion_generacion(self, generation, loc):
        if generation != self._location_request_generation:
            return
        self._location_request_in_progress = False
        self._location_cancel = None
        self._on_ubicacion(loc)

    def _on_error_ubicacion(self, generation, error):
        if generation != self._location_request_generation:
            return
        self._location_request_in_progress = False
        self._location_cancel = None
        self._ubicacion_actual = None
        self._open_map_when_located = False
        self._set_estado(error)
        self._refrescar_lista()

    def _actualizar_ubicacion_escritorio(self):
        loc = repartidor.obtener_ubicacion_actual()
        if loc:
            self._on_ubicacion(loc)
        else:
            self._open_map_when_located = False
            self._set_estado('No se pudo obtener la ubicación en este equipo.')

    def _on_ubicacion(self, loc):
        if not isinstance(loc, dict) or not repartidor.coordenadas_validas(
            loc.get('lat'), loc.get('lng')
        ):
            self._ubicacion_actual = None
            self._open_map_when_located = False
            self._set_estado(
                'No se recibió una ubicación válida. Comprueba que la ubicación '
                'esté activa y vuelve a intentarlo.'
            )
            return
        self._ubicacion_actual = loc
        self._set_estado(
            f'Depósito actual: {loc["lat"]:.5f}, {loc["lng"]:.5f}. '
            'La ruta saldrá y volverá exactamente aquí.'
        )
        self._refrescar_lista()
        if self._open_map_when_located:
            self._open_map_when_located = False
            self.abrir_google_maps()

    # ------------------------------------------------------------------
    # Reloj 18:45
    # ------------------------------------------------------------------
    def _programar_reloj_19(self):
        """Recalcula la ruta cada minuto para aplicar la regla de las 18:45."""
        if Clock:
            self._clock_19 = Clock.schedule_interval(self._verificar_hora_19, 60)

    def _verificar_hora_19(self, *_args):
        hora = _hora_actual()
        if hora >= 1125 and self.lista_paradas:  # 18:45
            self._set_estado('🕖 Son las 18:45 – reordenando por prioridad…')
            self._refrescar_lista()

    # ------------------------------------------------------------------
    # Entrada de paradas
    # ------------------------------------------------------------------
    def mostrar_acciones_parada(self, *_args):
        if Popup is object:
            self._set_estado(
                'Usa el botón integrado de la app para abrir cámara, lupa o micrófono.'
            )
            return

        if self._popup_acciones_parada is not None:
            self._popup_acciones_parada.dismiss()
            self._popup_acciones_parada = None

        contenido = BoxLayout(orientation='vertical', padding=12, spacing=10)
        contenido.add_widget(Label(
            text='Elige cómo añadir la parada',
            size_hint_y=None,
            height='36dp',
            halign='center',
        ))
        entrada = TextInput(
            text=(self.txt_busqueda.text or '') if self.txt_busqueda else '',
            hint_text='Escribir dirección…',
            multiline=False,
            size_hint_y=None,
            height='52dp',
            padding=(10, 13),
        )
        contenido.add_widget(entrada)

        acciones_manual = BoxLayout(size_hint_y=None, height='52dp', spacing=8)
        btn_lupa = Button(
            text='🔍 Añadir parada',
            background_normal='',
            background_color=(0.95, 0.55, 0.1, 1),
        )
        btn_lupa.bind(
            on_press=lambda *_args: self._buscar_manual_desde_popup(
                self._popup_acciones_parada, entrada
            )
        )
        acciones_manual.add_widget(btn_lupa)
        contenido.add_widget(acciones_manual)

        acciones = BoxLayout(size_hint_y=None, height='56dp', spacing=8)
        for texto, color, accion in (
            ('🎙 Micrófono', (0.2, 0.7, 0.3, 1), self.dictar_microfono),
            ('📷 Escáner', (0.1, 0.6, 0.9, 1), self.escanear_camara),
        ):
            boton = Button(
                text=texto,
                background_normal='',
                background_color=color,
            )
            boton.bind(
                on_press=lambda *_args, handler=accion: self._ejecutar_accion_integrada(
                    self._popup_acciones_parada, handler
                )
            )
            acciones.add_widget(boton)
        contenido.add_widget(acciones)

        cerrar = Button(text='Cerrar', size_hint_y=None, height='48dp')
        contenido.add_widget(cerrar)
        popup = Popup(
            title='Añadir parada',
            content=contenido,
            size_hint=(0.92, None),
            height='320dp',
            auto_dismiss=False,
        )
        self._popup_acciones_parada = popup
        cerrar.bind(on_press=lambda *_args: self._cerrar_popup_acciones_parada(popup))
        entrada.bind(
            on_text_validate=lambda *_args: self._buscar_manual_desde_popup(
                popup, entrada
            )
        )
        popup.open()

    def _cerrar_popup_acciones_parada(self, popup):
        popup.dismiss()
        if self._popup_acciones_parada is popup:
            self._popup_acciones_parada = None

    def _ejecutar_accion_integrada(self, popup, accion):
        self._cerrar_popup_acciones_parada(popup)
        accion()

    def _buscar_manual_desde_popup(self, popup, entrada, *_args):
        if self.txt_busqueda is not None:
            self.txt_busqueda.text = entrada.text
        if self.buscar_manual():
            self._cerrar_popup_acciones_parada(popup)

    def escanear_camara(self, *_args):
        """Take a photo and propose its OCR address for confirmation."""
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
        if self._camera_en_curso:
            self._set_estado('Ya hay una captura de cámara en curso.')
            return
        self._set_estado('Abriendo cámara…')
        filepath = os.path.join(self.user_data_dir, 'temp_scan.jpg')
        self._temp_scan_path = filepath
        self._camera_en_curso = True
        self._eliminar_temporal(filepath)
        android_services.capture_photo(
            filepath,
            self._procesar_foto,
            lambda error: self._error_captura(error, filepath),
        )

    def _procesar_foto(self, filepath):
        filepath = filepath or os.path.join(self.user_data_dir, 'temp_scan.jpg')
        if not os.path.isfile(filepath):
            self._camera_en_curso = False
            self._set_estado('No se capturó ninguna imagen.')
            self._temp_scan_path = None
            return
        self._set_estado('Procesando imagen…')
        if android_services.is_android():
            android_services.recognize_image_text(
                filepath,
                lambda texto: self._procesar_texto_ocr(texto, filepath),
                lambda error: self._error_captura(error, filepath),
            )
            return
        texto = repartidor.leer_texto_imagen(filepath)
        self._procesar_texto_ocr(texto, filepath)

    def _procesar_texto_ocr(self, texto, filepath):
        try:
            componentes = repartidor.construir_direccion_estructurada(texto)
            direccion_completa = componentes.get('direccion_completa', '').strip()
            if direccion_completa:
                self._set_estado(
                    f'Dirección detectada: {direccion_completa}. Geocodificando…'
                )
                self._ejecutar_en_segundo_plano(
                    lambda: self._geocodificar_y_abrir_ocr(componentes)
                )
            else:
                candidatos = repartidor.extraer_candidatos_direccion_ocr(texto)
                if candidatos:
                    self._mostrar_confirmacion(candidatos, 'cámara')
                else:
                    self._set_estado('No se detectó una dirección válida en la imagen.')
        finally:
            self._eliminar_temporal(filepath)
            self._temp_scan_path = None
            self._camera_en_curso = False

    def _geocodificar_y_abrir_ocr(self, componentes):
        """Geocode structured OCR address, add stop, and open Maps automatically."""
        direccion_completa = componentes.get('direccion_completa', '')
        resultado, detalle = repartidor.resolver_geocodificacion(
            direccion_completa,
            geocodificador=repartidor.buscar_direccion_texto,
        )
        self._dispatch_ui(
            lambda: self._finalizar_ocr(componentes, resultado, detalle)
        )

    def _finalizar_ocr(self, componentes, resultado, detalle):
        direccion_completa = componentes.get('direccion_completa', '')
        if not isinstance(resultado, dict) or not repartidor.coordenadas_validas(
            resultado.get('lat'), resultado.get('lng')
        ):
            self._set_estado(
                f'No se geocodificó "{direccion_completa}". '
                f'{detalle or "Comprueba la dirección, la conexión y la API key."}'
            )
            return
        # Verificar límite de versión prueba
        if self._es_cuenta_trial() and len(self.lista_paradas) >= auth.TRIAL_MAX_PARADAS:
            self._set_estado(
                f'⚠ Versión prueba: máximo {auth.TRIAL_MAX_PARADAS} paradas. '
                'Hazte con la versión completa para añadir más.'
            )
            if Clock:
                Clock.schedule_once(self._mostrar_donacion, 0.1)
            else:
                self._mostrar_donacion()
            return
        prioridad = self.spinner_prioridad.text if self.spinner_prioridad else 'media'
        resultado['prioridad'] = prioridad
        resultado['paqueteria'] = self._paqueteria
        resultado['notificacion'] = self._notificacion
        resultado['estado'] = 'pendiente'
        resultado.setdefault('address', direccion_completa)
        self.lista_paradas.append(resultado)
        self._set_estado(
            f'Parada añadida desde cámara: {resultado["address"]}. Abriendo Maps…'
        )
        self._refrescar_lista()
        self._abrir_maps_ubicacion(resultado['lat'], resultado['lng'])

    def _abrir_maps_ubicacion(self, lat, lng):
        """Abre Google Maps centrado en las coordenadas dadas.

        Delega en ``android_services.open_map_url`` que maneja tanto el intent
        de Android como el fallback al navegador en escritorio.
        """
        url = f'https://www.google.com/maps/search/?api=1&query={lat},{lng}'
        android_services.open_map_url(url, self._set_estado)

    def _usar_direccion_ocr(self, direccion, cp):
        if direccion and cp:
            texto = f'{direccion}, {cp}'
        elif direccion:
            texto = direccion
        else:
            self._set_estado('No se detectó una dirección válida en la imagen.')
            return
        componentes = repartidor.construir_direccion_estructurada(texto)
        direccion_completa = componentes.get('direccion_completa') or texto
        self._mostrar_confirmacion([direccion_completa], 'cámara')

    def _error_captura(self, error, filepath):
        self._eliminar_temporal(filepath)
        self._temp_scan_path = None
        self._camera_en_curso = False
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
            self._mostrar_confirmacion([texto], 'micrófono')
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
            lambda texto: self._mostrar_confirmacion([texto], 'micrófono'),
            self._set_estado,
        )

    def buscar_manual(self, *_args):
        """Geocodifica la dirección escrita manualmente."""
        texto = (self.txt_busqueda.text or '').strip() if self.txt_busqueda else ''
        if not texto:
            self._set_estado('Escribe una dirección primero.')
            return False
        resultado = self._validar_y_anadir(texto, 'búsqueda')
        if resultado and self.txt_busqueda:
            self.txt_busqueda.text = ''
        return bool(resultado)

    # ------------------------------------------------------------------
    # Geocodificación y gestión de paradas
    # ------------------------------------------------------------------
    def _mostrar_confirmacion(self, candidatos, origen):
        candidatos = [
            repartidor.normalizar_direccion(candidato)
            for candidato in candidatos
            if repartidor.normalizar_direccion(candidato)
        ]
        if not candidatos:
            self._set_estado(f'No se recibió una dirección válida por {origen}.')
            return
        if self.txt_busqueda is not None:
            self.txt_busqueda.text = candidatos[0]
        if Popup is object:
            self._set_estado(
                f'Dirección detectada por {origen}: {candidatos[0]}. '
                'Revísala en el campo y pulsa la lupa.'
            )
            return

        contenido = BoxLayout(orientation='vertical', padding=12, spacing=10)
        contenido.add_widget(Label(
            text=f'Dirección detectada por {origen}.\nRevísala antes de añadirla:',
            size_hint_y=None,
            height='54dp',
            halign='center',
        ))
        entrada = TextInput(
            text=candidatos[0],
            multiline=False,
            size_hint_y=None,
            height='52dp',
            padding=(10, 13),
        )
        if len(candidatos) > 1:
            selector = Spinner(
                text=candidatos[0],
                values=candidatos,
                size_hint_y=None,
                height='48dp',
            )
            selector.bind(
                text=lambda _spinner, valor: self._seleccionar_candidato(
                    entrada, valor
                )
            )
            contenido.add_widget(selector)
        contenido.add_widget(entrada)
        feedback = Label(
            text='',
            size_hint_y=None,
            height='44dp',
            halign='center',
            color=(1, 0.35, 0.35, 1),
        )
        contenido.add_widget(feedback)
        acciones = BoxLayout(size_hint_y=None, height='52dp', spacing=10)
        cancelar = Button(text='Cancelar')
        anadir = Button(text='Añadir parada', background_color=(0.2, 0.7, 0.3, 1))
        acciones.add_widget(cancelar)
        acciones.add_widget(anadir)
        contenido.add_widget(acciones)
        alto = '374dp' if len(candidatos) > 1 else '314dp'
        popup = Popup(
            title='Confirmar dirección',
            content=contenido,
            size_hint=(0.92, None),
            height=alto,
            auto_dismiss=False,
        )
        self._popup_confirmacion = popup
        cancelar.bind(on_press=lambda *_args: self._cerrar_confirmacion(popup))
        anadir.bind(
            on_press=lambda *_args: self._confirmar_propuesta(
                popup, entrada, origen, feedback
            )
        )
        entrada.bind(
            on_text_validate=lambda *_args: self._confirmar_propuesta(
                popup, entrada, origen, feedback
            )
        )
        popup.open()
        self._set_estado(f'Confirma o edita la dirección detectada por {origen}.')

    @staticmethod
    def _seleccionar_candidato(entrada, valor):
        entrada.text = valor

    def _cerrar_confirmacion(self, popup):
        popup.dismiss()
        if self._popup_confirmacion is popup:
            self._popup_confirmacion = None
        self._set_estado('Adición cancelada. Puedes escribir otra dirección.')

    def _confirmar_propuesta(self, popup, entrada, origen, feedback):
        texto = repartidor.normalizar_direccion(entrada.text)
        if self.txt_busqueda is not None:
            self.txt_busqueda.text = texto
        if not self._validar_y_anadir(texto, origen):
            feedback.text = self.lbl_estado.text if self.lbl_estado is not None else (
                'No se pudo añadir la dirección.'
            )
            return
        popup.dismiss()
        if self._popup_confirmacion is popup:
            self._popup_confirmacion = None
        if self.txt_busqueda is not None:
            self.txt_busqueda.text = ''

    def _validar_y_anadir(self, texto, origen):
        # Verificar límite de versión prueba antes de añadir
        if self._es_cuenta_trial() and len(self.lista_paradas) >= auth.TRIAL_MAX_PARADAS:
            self._set_estado(
                f'⚠ Versión prueba: máximo {auth.TRIAL_MAX_PARADAS} paradas. '
                'Hazte con la versión completa para añadir más.'
            )
            if Clock:
                Clock.schedule_once(self._mostrar_donacion, 0.1)
            else:
                self._mostrar_donacion()
            return False
        prioridad = self.spinner_prioridad.text if self.spinner_prioridad else 'media'
        parada, error = repartidor.iniciar_alta_parada(
            self.lista_paradas,
            texto,
            origen=origen,
            prioridad=prioridad,
            paqueteria=self._paqueteria,
            notificacion=self._notificacion,
        )
        if error:
            self._set_estado(error)
            return False
        self._set_estado(
            f'Geolocalizando parada de {origen}: {parada.get("address", texto)}…'
        )
        self._refrescar_lista()
        self._ejecutar_en_segundo_plano(
            lambda: self._geocodificar_parada(parada, origen)
        )
        return True

    def _es_cuenta_trial(self):
        """Devuelve True si el usuario actual tiene cuenta de prueba."""
        if not self._usuario_actual:
            return False
        return auth.is_trial(self.user_data_dir, self._usuario_actual)

    def _geocodificar_parada(self, parada, origen):
        resultado, detalle = repartidor.resolver_geocodificacion(
            parada.get('address', ''),
            geocodificador=repartidor.buscar_direccion_texto,
        )
        self._dispatch_ui(
            lambda: self._aplicar_geocodificacion(
                resultado, detalle, parada, origen
            )
        )

    def _aplicar_geocodificacion(self, resultado, detalle, parada, origen):
        if parada not in self.lista_paradas:
            return
        resultado, error = repartidor.aplicar_alta_geocodificada(
            self.lista_paradas, parada, resultado, detalle
        )
        if error:
            self._set_estado(
                f'Error al geolocalizar "{parada.get("address", "")}": {error} '
                'Puedes reintentar o corregirla.'
            )
        else:
            self._set_estado(
                f'Parada geolocalizada desde {origen}: {resultado["address"]}'
            )
        self._refrescar_lista()

    def _reintentar_geocodificacion(self, parada):
        if parada not in self.lista_paradas:
            return
        parada['estado'] = 'geolocalizando'
        parada.pop('error', None)
        self._set_estado(f'Reintentando geolocalización: {parada["address"]}…')
        self._refrescar_lista()
        self._ejecutar_en_segundo_plano(
            lambda: self._geocodificar_parada(
                parada, parada.get('origen', 'reintento')
            )
        )

    def _corregir_parada(self, parada):
        if parada not in self.lista_paradas:
            return
        if self.txt_busqueda is not None:
            self.txt_busqueda.text = parada.get('address', '')
            if hasattr(self.txt_busqueda, 'focus'):
                self.txt_busqueda.focus = True
        self.lista_paradas.remove(parada)
        self._set_estado(
            'Corrige la dirección en el campo y pulsa la lupa para geolocalizarla.'
        )
        self._refrescar_lista()

    def _geocodificar_y_añadir(self, texto):
        """Compatibility wrapper for callers using the former shared path."""
        return self._validar_y_anadir(texto, 'entrada')

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
            estado = parada.get('estado', 'pendiente')
            fila = BoxLayout(size_hint_y=None, height='52dp', spacing=4)
            color = repartidor.PRIORITY_COLORS.get(
                parada.get('prioridad', 'media'),
                repartidor.PRIORITY_COLORS['media'],
            )
            lbl = Label(
                text=(
                    f"[{parada.get('prioridad','?')}] "
                    f"{parada.get('address','Sin dirección')}\n"
                    f"Estado: {estado}"
                ),
                halign='left',
                font_size='12sp',
                size_hint_x=0.65 if estado == 'error' else 0.8,
                text_size=(None, None),
                color=color,
            )
            btn_del = Button(
                text='✕',
                size_hint_x=0.15 if estado == 'error' else 0.2,
                background_normal='',
                background_color=color,
            )
            real_idx = self.lista_paradas.index(parada) if parada in self.lista_paradas else -1
            btn_del.bind(on_press=lambda _btn, i=real_idx: self._eliminar_parada(i))
            fila.add_widget(lbl)
            if estado == 'error':
                btn_retry = Button(text='↻', size_hint_x=0.1)
                btn_edit = Button(text='✎', size_hint_x=0.1)
                btn_retry.bind(
                    on_press=lambda _btn, p=parada: self._reintentar_geocodificacion(p)
                )
                btn_edit.bind(
                    on_press=lambda _btn, p=parada: self._corregir_parada(p)
                )
                fila.add_widget(btn_retry)
                fila.add_widget(btn_edit)
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
        self._paqueteria = repartidor.normalizar_paqueteria(valor)
        spinner.text = self._paqueteria
        self._set_estado(f'Paquetería seleccionada: {valor}')

    def _on_notificacion_cambio(self, spinner, valor):
        if valor == _SELECT_CARTAS:
            return
        self._notificacion = repartidor.normalizar_cartas(valor)
        spinner.text = _SELECT_CARTAS
        self._set_estado(f'Cartas: {self._notificacion}')

    # ------------------------------------------------------------------
    # Abrir Maps
    # ------------------------------------------------------------------
    def abrir_google_maps(self, *_args):
        if not self.lista_paradas:
            self._set_estado('Añade al menos una dirección antes de crear la ruta.')
            return
        if android_services.is_android() and not android_services.is_location_enabled():
            self._open_map_when_located = True
            self._mostrar_dialogo_activar_ubicacion()
            return
        if not repartidor.coordenadas_validas(
            (self._ubicacion_actual or {}).get('lat'),
            (self._ubicacion_actual or {}).get('lng'),
        ):
            self._open_map_when_located = True
            self._set_estado('Obteniendo la posición GPS actual antes de abrir la ruta…')
            self.solicitar_ubicacion()
            return
        pendientes = [
            parada for parada in self.lista_paradas
            if parada.get('estado') == 'geolocalizando'
            or not repartidor.coordenadas_validas(
                parada.get('lat'), parada.get('lng')
            )
        ]
        if pendientes:
            estados = {parada.get('estado') for parada in pendientes}
            if 'geolocalizando' in estados:
                mensaje = (
                    'Espera: aún hay paradas geolocalizándose antes de optimizar.'
                )
            else:
                mensaje = (
                    'Hay paradas sin coordenadas válidas. Reintenta, corrige o '
                    'elimina las que muestran error.'
                )
            self._set_estado(mensaje)
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
            self._open_map_when_located = False
            if android_services.is_android():
                android_services.open_map_url(url, self._set_estado)
            else:
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
    def _ejecutar_en_segundo_plano(callback):
        threading.Thread(target=callback, daemon=True).start()

    @staticmethod
    def _dispatch_ui(callback):
        if Clock:
            Clock.schedule_once(lambda _delta: callback(), 0)
        else:
            callback()

    @staticmethod
    def _eliminar_temporal(filepath):
        try:
            if os.path.isfile(filepath):
                os.remove(filepath)
        except OSError:
            pass

    def on_stop(self):
        if self._clock_19 is not None:
            self._clock_19.cancel()
            self._clock_19 = None
        if self._popup_confirmacion is not None:
            self._popup_confirmacion.dismiss()
            self._popup_confirmacion = None
        if self._popup_acciones_parada is not None:
            self._popup_acciones_parada.dismiss()
            self._popup_acciones_parada = None
        if self._temp_scan_path:
            self._eliminar_temporal(self._temp_scan_path)
            self._temp_scan_path = None
        self._camera_en_curso = False
        android_services.cancel_pending_activities()

    def on_pause(self):
        self._resume_location_after_pause = self._location_request_in_progress
        self._location_request_generation += 1
        self._location_request_in_progress = False
        if self._location_cancel is not None:
            self._location_cancel()
            self._location_cancel = None
        else:
            android_services.cancel_location_request()
        return True

    def on_resume(self):
        if not android_services.is_android():
            return
        if self._waiting_location_settings:
            self._waiting_location_settings = False
            if android_services.is_location_enabled():
                self._location_dialog_shown = False
                self._set_estado('Ubicación activada. Obteniendo posición actual…')
                self._comprobar_proveedor_y_localizar(prompt_settings=False)
            else:
                self._set_estado(
                    'La ubicación sigue apagada. Abre la ruta cuando quieras '
                    'volver a abrir Ajustes.'
                )
            self._resume_location_after_pause = False
        elif self._resume_location_after_pause:
            self._resume_location_after_pause = False
            if (
                android_services.location_permission_granted()
                and android_services.is_location_enabled()
            ):
                self._set_estado('Reanudando la obtención de tu posición actual…')
                self._iniciar_localizacion()


if __name__ == '__main__':
    app = RepartidorApp()
    if hasattr(app, 'run'):
        app.run()
