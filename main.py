"""Aplicación principal del repartidor con autenticación y flujo de procesamiento."""
import hashlib
import json
import os
import sys

try:
    import repartidor  # type: ignore
except ImportError:
    repartidor = None  # type: ignore

try:
    from kivy.app import App
    from kivy.uix.boxlayout import BoxLayout
    from kivy.uix.label import Label
    from kivy.uix.button import Button
    from kivy.uix.textinput import TextInput
except ImportError:
    App = object
    BoxLayout = object
    Label = object
    Button = object
    TextInput = object

sys.path.insert(0, os.path.dirname(__file__))

USERS_FILE = os.path.join(os.path.dirname(__file__), 'users.json')


class _FallbackBoxLayout:
    """Sustituto de BoxLayout cuando Kivy no está disponible."""

    def __init__(self, **kwargs):
        self.children = []
        self.orientation = kwargs.get('orientation', 'vertical')
        self.padding = kwargs.get('padding', 0)
        self.spacing = kwargs.get('spacing', 0)

    def add_widget(self, widget):
        """Añade un widget hijo a la lista."""
        self.children.append(widget)

    def clear_widgets(self):
        """Elimina todos los widgets hijos."""
        self.children.clear()


class _FallbackLabel:
    """Sustituto de Label cuando Kivy no está disponible."""

    def __init__(self, text='', **kwargs):
        """Inicializa la etiqueta con texto y opciones de estilo."""
        self.text = text
        self.size_hint_y = kwargs.get('size_hint_y', None)
        self.height = kwargs.get('height', 0)
        self.font_size = kwargs.get('font_size', 14)


class _FallbackButton:
    """Sustituto de Button cuando Kivy no está disponible."""

    def __init__(self, text='', **kwargs):
        """Inicializa el botón con texto y opciones de estilo."""
        self.text = text
        self.size_hint_y = kwargs.get('size_hint_y', None)
        self.height = kwargs.get('height', 0)
        self.binded = []

    def bind(self, **kwargs):
        """Registra callbacks de eventos del botón."""
        if 'on_press' in kwargs:
            self.binded.append(kwargs['on_press'])


class _FallbackTextInput:
    """Sustituto de TextInput cuando Kivy no está disponible."""

    def __init__(self, **kwargs):
        """Inicializa el campo de texto con sus opciones."""
        self.text = kwargs.get('text', '')
        self.password = kwargs.get('password', False)
        self.multiline = kwargs.get('multiline', True)


if BoxLayout is object:
    BoxLayout = _FallbackBoxLayout
if Label is object:
    Label = _FallbackLabel
if Button is object:
    Button = _FallbackButton
if TextInput is object:
    TextInput = _FallbackTextInput


def _hash_password(password):
    """Devuelve el hash SHA-256 de la contraseña."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def cargar_usuarios():
    """Carga y devuelve el diccionario de usuarios desde el archivo JSON."""
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, encoding='utf-8') as handle:
            data = json.load(handle)
    except (IOError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def guardar_usuarios(usuarios):
    """Persiste el diccionario de usuarios en el archivo JSON."""
    with open(USERS_FILE, 'w', encoding='utf-8') as handle:
        json.dump(usuarios, handle, indent=2, ensure_ascii=False)


def _get_user_record(usuario):
    """Devuelve el diccionario completo y el registro del usuario indicado."""
    usuarios = cargar_usuarios()
    entry = usuarios.get(usuario)
    if isinstance(entry, dict):
        return usuarios, entry
    if isinstance(entry, str):
        return usuarios, {'password': entry, 'recovery_answer': None}
    return usuarios, None


def registrar_usuario(usuario, password, recovery_answer=''):
    """Crea una cuenta nueva."""
    usuario = usuario.strip()
    password = password.strip()
    recovery_answer = recovery_answer.strip()
    if not usuario or not password:
        return False, 'Usuario y contraseña son obligatorios.'
    if not recovery_answer:
        return False, 'Debes indicar una respuesta secreta para recuperar la contraseña.'

    usuarios = cargar_usuarios()
    if usuario in usuarios:
        return False, 'El usuario ya existe. Prueba a iniciar sesión.'

    usuarios[usuario] = {
        'password': _hash_password(password),
        'recovery_answer': _hash_password(recovery_answer.lower())
    }
    guardar_usuarios(usuarios)
    return True, 'Cuenta creada correctamente. Ya puedes iniciar sesión.'


def autenticar_usuario(usuario, password):
    """Valida contraseña."""
    usuario = usuario.strip()
    password = password.strip()
    if not usuario or not password:
        return False, 'Usuario y contraseña son obligatorios.', None

    usuarios, entry = _get_user_record(usuario)
    if entry is None:
        return False, 'Usuario no encontrado. Regístrate para continuar.', None

    stored_hash = entry.get('password')
    if stored_hash != _hash_password(password):
        return False, 'La contraseña es incorrecta.', None

    usuarios[usuario] = entry
    guardar_usuarios(usuarios)
    return True, 'Acceso correcto.', 'ok'


def recuperar_password(usuario, recovery_answer, new_password):
    """Restablece la contraseña verificando la respuesta secreta."""
    usuario = usuario.strip()
    recovery_answer = recovery_answer.strip().lower()
    new_password = new_password.strip()
    if not usuario or not recovery_answer or not new_password:
        return False, 'Usuario, respuesta secreta y nueva contraseña son obligatorios.'

    usuarios, entry = _get_user_record(usuario)
    if entry is None:
        return False, 'Usuario no encontrado.'

    if not entry.get('recovery_answer'):
        return False, 'Este usuario no tiene una respuesta de recuperación guardada.'

    if entry.get('recovery_answer') != _hash_password(recovery_answer):
        return False, 'La respuesta secreta es incorrecta.'

    usuarios[usuario] = {
        'password': _hash_password(new_password),
        'recovery_answer': entry.get('recovery_answer')
    }
    guardar_usuarios(usuarios)
    return True, 'Contraseña restablecida correctamente.'


class RepartidorLayout(BoxLayout):
    """Layout principal de la aplicación con autenticación y procesamiento."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = 20
        self.spacing = 10

        self.register_mode = False
        self.recovery_mode = False
        self.username_input = TextInput(multiline=False)
        self.password_input = TextInput(multiline=False, password=True)
        self.recovery_answer_input = TextInput(multiline=False)
        self.status_label = Label(
            text='Introduce tus datos para entrar', size_hint_y=None, height=40)
        self.result = Label(text='Pulsa para procesar',
                            size_hint_y=None, height=80)

        self._build_auth_view()

    def _build_auth_view(self):
        """Construye la vista de login o registro."""
        self.clear_widgets()
        self.add_widget(Label(text='Repartidor', font_size=24,
                              size_hint_y=None, height=50))
        self.add_widget(self.status_label)

        self.add_widget(Label(text='Usuario', size_hint_y=None, height=30))
        self.add_widget(self.username_input)
        label_text = 'Nueva contraseña' if self.recovery_mode else 'Contraseña'
        self.add_widget(Label(text=label_text, size_hint_y=None, height=30))
        self.add_widget(self.password_input)

        if self.register_mode or self.recovery_mode:
            self.add_widget(Label(text='Respuesta secreta',
                                  size_hint_y=None, height=30))
            self.add_widget(self.recovery_answer_input)

        if self.recovery_mode:
            action_text = 'Restablecer contraseña'
        elif self.register_mode:
            action_text = 'Crear cuenta'
        else:
            action_text = 'Entrar'

        action_button = Button(text=action_text, size_hint_y=None, height=60)
        action_button.bind(on_press=self.handle_auth)
        self.add_widget(action_button)

        in_alt_mode = self.register_mode or self.recovery_mode
        toggle_text = 'Volver al inicio de sesión' if in_alt_mode else 'Crear cuenta'
        toggle_button = Button(text=toggle_text, size_hint_y=None, height=50)
        toggle_button.bind(on_press=self.toggle_register)
        self.add_widget(toggle_button)

        if not self.register_mode and not self.recovery_mode:
            recovery_button = Button(
                text='He olvidado la contraseña', size_hint_y=None, height=50)
            recovery_button.bind(on_press=self.toggle_recovery)
            self.add_widget(recovery_button)

    def _build_main_view(self):
        """Construye la vista principal tras iniciar sesión."""
        self.clear_widgets()
        self.add_widget(Label(text='Repartidor', font_size=24,
                              size_hint_y=None, height=50))
        self.add_widget(self.result)

        btn = Button(text='Procesar imagen', size_hint_y=None, height=60)
        btn.bind(on_press=self.procesar)
        self.add_widget(btn)

        logout_btn = Button(text='Cerrar sesión', size_hint_y=None, height=50)
        logout_btn.bind(on_press=self.volver_a_auth)
        self.add_widget(logout_btn)

    def toggle_register(self, _instance):
        """Alterna entre el modo registro y el inicio de sesión."""
        if self.register_mode or self.recovery_mode:
            self.register_mode = False
            self.recovery_mode = False
            self.status_label.text = 'Introduce tus datos para entrar'
        else:
            self.register_mode = True
            self.recovery_mode = False
            self.status_label.text = 'Regístrate para crear una cuenta nueva'
        self._build_auth_view()

    def toggle_recovery(self, _instance):
        """Activa el modo de recuperación de contraseña."""
        self.register_mode = False
        self.recovery_mode = True
        self.status_label.text = 'Recupera tu contraseña con la respuesta secreta'
        self._build_auth_view()

    def handle_auth(self, _instance):
        """Gestiona el envío del formulario de autenticación."""
        if self.recovery_mode:
            ok, message = recuperar_password(
                self.username_input.text,
                self.recovery_answer_input.text,
                self.password_input.text)
            self.status_label.text = message
            if ok:
                self._reset_inputs()
                self.register_mode = False
                self.recovery_mode = False
                self.status_label.text = 'Contraseña restablecida. Inicia sesión.'
                self._build_auth_view()
        elif self.register_mode:
            ok, message = registrar_usuario(
                self.username_input.text,
                self.password_input.text,
                self.recovery_answer_input.text)
            self.status_label.text = message
            if ok:
                self._reset_inputs()
                self.register_mode = False
                self.status_label.text = message
                self._build_auth_view()
        else:
            ok, message, _estado = autenticar_usuario(
                self.username_input.text, self.password_input.text)
            self.status_label.text = message
            if ok:
                self._reset_inputs()
                self._build_main_view()

    def _reset_inputs(self):
        """Limpia todos los campos de texto del formulario."""
        self.username_input.text = ''
        self.password_input.text = ''
        self.recovery_answer_input.text = ''

    def volver_a_auth(self, _instance):
        """Cierra la sesión y vuelve a la pantalla de autenticación."""
        self._reset_inputs()
        self.register_mode = False
        self.recovery_mode = False
        self.status_label.text = 'Introduce tus datos para entrar'
        self._build_auth_view()

    def procesar(self, _instance):
        """Procesa la imagen de dirección y muestra las coordenadas."""
        try:
            direccion, cp = repartidor.procesar_imagen('foto_direccion.jpg')
            geo = repartidor.obtener_coordenadas(direccion, cp)
            if geo:
                self.result.text = f"{geo['address']}"
            else:
                self.result.text = 'No se pudo obtener coordenadas'
        except (ValueError, KeyError, AttributeError) as e:
            self.result.text = f'Error: {e}'


class RepartidorApp(App):
    """Aplicación Kivy del repartidor."""

    def build(self):
        """Crea y devuelve el widget raíz de la aplicación."""
        return RepartidorLayout()

    def run(self):
        """Arranca la app; usa modo consola si Kivy no está disponible."""
        no_kivy = (BoxLayout.__module__ == '_fallback_boxlayout'
                   or BoxLayout.__name__ == '_FallbackBoxLayout')
        if no_kivy:
            print('Kivy no está instalado; se ejecuta en modo consola.')
            print('--- Inicio de sesión ---')
            try:
                usuario = input('Usuario: ').strip()
                password = input('Contraseña: ').strip()
                ok, message, _estado = autenticar_usuario(usuario, password)
                if not ok:
                    if 'Usuario no encontrado' in message:
                        registrar = input(
                            '¿Deseas registrarte? [s/n]: ').strip().lower()
                        if registrar in {'s', 'si', 'yes', 'y'}:
                            answer = input(
                                'Respuesta secreta para crear la cuenta: ').strip()
                            ok, message = registrar_usuario(
                                usuario, password, answer)
                            print(message)
                            print('Vuelve a ejecutar la app para iniciar sesión.')
                            return
                        print('Operación cancelada.')
                        return

                    recuperar = input(
                        '¿Olvidaste la contraseña? [s/n]: ').strip().lower()
                    if recuperar in {'s', 'si', 'yes', 'y'}:
                        answer = input('Respuesta secreta: ').strip()
                        new_password = input('Nueva contraseña: ').strip()
                        ok, message = recuperar_password(
                            usuario, answer, new_password)
                        print(message)
                        return

                    print(message)
                    return

                print(message)
                print('--- Procesando dirección ---')
                direccion, cp = repartidor.procesar_imagen('foto_direccion.jpg')
                geo = repartidor.obtener_coordenadas(direccion, cp)
                if geo:
                    print('Coordenadas obtenidas:')
                    print(geo)
                else:
                    print('No se pudo obtener coordenadas')
            except (ValueError, OSError, RuntimeError) as e:
                print(f'Error: {e}')
            return
        super().run()


if __name__ == '__main__':
    RepartidorApp().run()
