"""
App de autenticación con auto-relleno de código OTP via SMS Retriever.
"""

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.clock import Clock, mainthread
from kivy.metrics import dp

from sms_receiver import SMSAutoReader


# ─────────────────────────────────────────────
# Pantalla de verificación OTP
# ─────────────────────────────────────────────

class VerificacionScreen(Screen):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._sms_reader = None
        self._build_ui()

    def _build_ui(self):
        layout = BoxLayout(
            orientation='vertical',
            padding=dp(30),
            spacing=dp(20),
        )

        layout.add_widget(Label(
            text='Verificación',
            font_size=dp(26),
            bold=True,
            size_hint_y=None,
            height=dp(50),
        ))

        layout.add_widget(Label(
            text='Se ha enviado un código a tu teléfono.\nSe rellenará automáticamente.',
            font_size=dp(15),
            halign='center',
            size_hint_y=None,
            height=dp(60),
        ))

        self.otp_input = TextInput(
            hint_text='Código OTP',
            multiline=False,
            input_filter='int',
            font_size=dp(24),
            halign='center',
            size_hint_y=None,
            height=dp(60),
        )
        layout.add_widget(self.otp_input)

        self.status_label = Label(
            text='Esperando código SMS...',
            font_size=dp(13),
            color=(0.5, 0.5, 0.5, 1),
            size_hint_y=None,
            height=dp(30),
        )
        layout.add_widget(self.status_label)

        btn_verificar = Button(
            text='Verificar',
            size_hint_y=None,
            height=dp(50),
            background_color=(0.2, 0.6, 1, 1),
        )
        btn_verificar.bind(on_press=self.verificar_codigo)
        layout.add_widget(btn_verificar)

        btn_reenviar = Button(
            text='Reenviar código',
            size_hint_y=None,
            height=dp(45),
            background_color=(0.7, 0.7, 0.7, 1),
        )
        btn_reenviar.bind(on_press=self.reenviar_codigo)
        layout.add_widget(btn_reenviar)

        layout.add_widget(Label())  # spacer
        self.add_widget(layout)

    # ── Ciclo de vida de la pantalla ──────────────────────

    def on_enter(self):
        """Inicia el SMS Retriever al entrar a la pantalla."""
        self._sms_reader = SMSAutoReader(on_otp_received=self._on_otp_recibido)
        self._sms_reader.start()
        self._set_status('Esperando código SMS...')

    def on_leave(self):
        """Detiene el SMS Retriever al salir de la pantalla."""
        if self._sms_reader:
            self._sms_reader.stop()
            self._sms_reader = None

    # ── Callbacks ────────────────────────────────────────

    @mainthread
    def _on_otp_recibido(self, code: str):
        """Se llama automáticamente cuando el SMS llega con el código."""
        self.otp_input.text = code
        self._set_status(f'Código detectado automáticamente ✓')
        # Verificar automáticamente tras 0.5 s si el campo está relleno
        Clock.schedule_once(lambda dt: self.verificar_codigo(None), 0.5)

    def verificar_codigo(self, instance):
        code = self.otp_input.text.strip()
        if not code:
            self._set_status('Introduce el código.')
            return
        # TODO: aquí llamas a Firebase verify / tu backend
        self._set_status(f'Verificando código {code}...')
        print(f"[Auth] Verificando código: {code}")

    def reenviar_codigo(self, instance):
        self.otp_input.text = ''
        if self._sms_reader:
            self._sms_reader.stop()
        self._sms_reader = SMSAutoReader(on_otp_received=self._on_otp_recibido)
        self._sms_reader.start()
        self._set_status('Código reenviado. Esperando SMS...')

    def _set_status(self, text: str):
        self.status_label.text = text


# ─────────────────────────────────────────────
# App principal
# ─────────────────────────────────────────────

class RepartidorApp(App):

    def build(self):
        sm = ScreenManager()
        sm.add_widget(VerificacionScreen(name='verificacion'))
        return sm


if __name__ == '__main__':
    RepartidorApp().run()
