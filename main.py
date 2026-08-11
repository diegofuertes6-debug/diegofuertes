"""Aplicación principal del repartidor con autenticación y captura de fotos."""

import hashlib
import importlib
import json
import os

import repartidor

try:
    App = importlib.import_module('kivy.app').App
    BoxLayout = importlib.import_module('kivy.uix.boxlayout').BoxLayout
    Label = importlib.import_module('kivy.uix.label').Label
    Button = importlib.import_module('kivy.uix.button').Button
    TextInput = importlib.import_module('kivy.uix.textinput').TextInput
    get_platform = importlib.import_module('kivy.utils').platform
    dp = importlib.import_module('kivy.metrics').dp
    Window = importlib.import_module('kivy.core.window').Window
except Exception:
    class App:
        def run(self):
            raise RuntimeError('Kivy no está instalado en este entorno')

    class BoxLayout:
        def __init__(self, **kwargs):
            self.kwargs = kwargs
            self._widgets = []

        def add_widget(self, widget):
            self._widgets.append(widget)

        def clear_widgets(self):
            self._widgets.clear()

    class Label:
        def __init__(self, **kwargs):
            self.text = kwargs.get('text', '')
            self.color = kwargs.get('color', (1, 1, 1, 1))

        def bind(self, *_args, **_kwargs):
            return None

        def setter(self, attr):
            def _setter(instance, value):
                setattr(instance, attr, value)

            return _setter

    class Button:
        def __init__(self, **kwargs):
            self.text = kwargs.get('text', '')

        def bind(self, *_args, **_kwargs):
            return None

    class TextInput:
        def __init__(self, **kwargs):
            self.text = ''
            self.hint_text = kwargs.get('hint_text', '')
            self.password = kwargs.get('password', False)

    class Window:
        softinput_mode = 'below_target'

    def get_platform():
        return ''

    def dp(value):
        return value


Window.softinput_mode = 'below_target'


class UserManager:
    """Persistencia simple de usuarios con hash de contraseñas."""

    def __init__(self):
        self.file_path = self._get_storage_path()
        self._ensure_path_exists()

    def _get_storage_path(self):
        if get_platform() == 'android':
            try:
                Python = importlib.import_module('com.chaquo.python').Python
                context = Python.getPlatform().getApplication()
                return os.path.join(str(context.getFilesDir().getAbsolutePath()), 'users.json')
            except (ImportError, AttributeError):
                return 'users.json'

        return os.path.join(os.path.dirname(__file__), 'users.json')

    def _ensure_path_exists(self):
        directory = os.path.dirname(self.file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

    def hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    def load_users(self):
        if not os.path.exists(self.file_path):
            return {}

        try:
            with open(self.file_path, 'r', encoding='utf-8') as handle:
                return json.load(handle)
        except (json.JSONDecodeError, IOError):
            return {}

    def save_users(self, users):
        try:
            with open(self.file_path, 'w', encoding='utf-8') as handle:
                json.dump(users, handle, indent=4, ensure_ascii=False)
            return True
        except IOError as exc:
            print(f'Error al guardar datos: {exc}')
            return False


class RepartidorLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.user_manager = UserManager()
        self._setup_ui()

    def _setup_ui(self):
        self.orientation = 'vertical'
        self.padding = dp(25)
        self.spacing = dp(15)

        self.add_widget(Label(
            text='SISTEMA REPARTIDOR',
            font_size='26sp',
            bold=True,
            size_hint_y=None,
            height=dp(100),
            color=(0.12, 0.58, 0.95, 1),
        ))

        self.username = self._create_input('Usuario')
        self.password = self._create_input('Contraseña', is_password=True)

        self.add_widget(self.username)
        self.add_widget(self.password)

        self._add_button('INICIAR SESIÓN', self.do_login, (0.12, 0.58, 0.95, 1), dp(60))
        self._add_button('¿No tienes cuenta? Regístrate', self.do_register, (0.95, 0.95, 0.95, 1), dp(40))
        self._add_button('Tomar foto', self.take_photo, (0.2, 0.7, 0.2, 1), dp(50))

        self.status = Label(text='Bienvenido', halign='center', font_size='14sp')
        self.status.bind(size=self.status.setter('text_size'))
        self.add_widget(self.status)

    def _add_button(self, text, handler, background_color, height):
        button = Button(
            text=text,
            bold=True,
            size_hint_y=None,
            height=height,
            background_color=background_color,
        )
        button.bind(on_press=handler)
        self.add_widget(button)
        return button

    def _create_input(self, hint, is_password=False):
        return TextInput(
            hint_text=hint,
            password=is_password,
            multiline=False,
            write_tab=False,
            size_hint_y=None,
            height=dp(50),
            padding=[dp(10), dp(12), dp(10), dp(12)],
        )

    def update_status(self, text, color=(1, 1, 1, 1)):
        if hasattr(self, 'status'):
            self.status.text = text
            self.status.color = color

    def _get_credentials(self):
        uid = self.username.text.strip() if hasattr(self, 'username') else ''
        pwd = self.password.text.strip() if hasattr(self, 'password') else ''
        return uid, pwd

    def do_login(self, _instance):
        uid, pwd = self._get_credentials()
        if not uid or not pwd:
            return self.update_status('Complete usuario y contraseña', (1, 0.3, 0.3, 1))

        users = self.user_manager.load_users()
        user_data = users.get(uid)
        expected_hash = self.user_manager.hash_password(pwd)

        if user_data and user_data.get('password') == expected_hash:
            self.update_status(f'¡Bienvenido, {uid}!', (0.3, 1, 0.3, 1))
        else:
            self.update_status('Credenciales incorrectas', (1, 0.3, 0.3, 1))

    def do_register(self, _instance):
        uid, pwd = self._get_credentials()
        if not uid or not pwd:
            return self.update_status('Datos incompletos', (1, 0.3, 0.3, 1))

        users = self.user_manager.load_users()
        if uid in users:
            self.update_status('El usuario ya existe', (1, 0.6, 0.2, 1))
            return

        users[uid] = {'password': self.user_manager.hash_password(pwd)}
        if self.user_manager.save_users(users):
            self.update_status('Registro exitoso. Inicie sesión.', (0.3, 1, 0.3, 1))
        else:
            self.update_status('No se pudo guardar el usuario', (1, 0.3, 0.3, 1))

    def take_photo(self, _instance):
        try:
            photo_path = repartidor.take_photo(repartidor.DEFAULT_PHOTO_FILENAME)
            self.update_status(f'Foto lista: {photo_path}', (0.3, 1, 0.3, 1))
        except Exception as exc:
            self.update_status(f'Error al abrir cámara: {exc}', (1, 0.3, 0.3, 1))


class RepartidorApp(App):
    def build(self):
        return RepartidorLayout()


def start_from_android():
    RepartidorApp().run()


if __name__ == '__main__':
    start_from_android()