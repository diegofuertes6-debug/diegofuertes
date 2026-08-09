"""
SMS Retriever para Android - detecta automáticamente el código OTP del SMS
y lo pasa a la app Kivy sin que el usuario lo escriba.
"""

import re

# Solo se ejecuta en Android
try:
    from jnius import autoclass, cast
    from android.broadcast import BroadcastReceiver
    from android import activity
    ANDROID = True
except ImportError:
    ANDROID = False


# Patrón para extraer código OTP de 4-8 dígitos del mensaje SMS
OTP_PATTERN = re.compile(r'\b(\d{4,8})\b')


def extract_otp(message: str) -> str | None:
    """Extrae el primer código numérico de 4-8 dígitos del mensaje SMS."""
    match = OTP_PATTERN.search(message)
    return match.group(1) if match else None


if ANDROID:
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    SmsRetrieverClient = autoclass('com.google.android.gms.auth.api.phone.SmsRetriever')
    Task = autoclass('com.google.android.gms.tasks.Task')

    class SMSAutoReader:
        """
        Usa la SMS Retriever API de Google para leer el código OTP
        automáticamente sin pedir permiso READ_SMS al usuario.
        """

        def __init__(self, on_otp_received):
            """
            on_otp_received: función callback(code: str) que se llama
            cuando se detecta el OTP.
            """
            self.on_otp_received = on_otp_received
            self._receiver = None

        def start(self):
            """Inicia el cliente SMS Retriever."""
            context = PythonActivity.mActivity
            client = SmsRetrieverClient.getClient(context)
            task = client.startSmsRetriever()
            task.addOnSuccessListener(self._on_retriever_started)
            task.addOnFailureListener(self._on_retriever_failed)

        def _on_retriever_started(self, result):
            """SMS Retriever listo — registramos el BroadcastReceiver."""
            self._receiver = BroadcastReceiver(
                self._on_sms_received,
                actions=['com.google.android.gms.auth.api.phone.SMS_RETRIEVED']
            )
            self._receiver.start()

        def _on_retriever_failed(self, exception):
            print(f"[SMSAutoReader] Error al iniciar SMS Retriever: {exception}")

        def _on_sms_received(self, context, intent):
            """Callback cuando llega el SMS con el código."""
            if intent is None:
                return

            extras = intent.getExtras()
            if extras is None:
                return

            message = extras.get('extraSmsMessage')
            if message:
                code = extract_otp(str(message))
                if code and self.on_otp_received:
                    self.on_otp_received(code)

        def stop(self):
            """Detiene el BroadcastReceiver."""
            if self._receiver:
                self._receiver.stop()
                self._receiver = None

else:
    # Stub para desarrollo en PC/Linux (no Android)
    class SMSAutoReader:
        def __init__(self, on_otp_received):
            self.on_otp_received = on_otp_received

        def start(self):
            print("[SMSAutoReader] SMS Retriever no disponible fuera de Android.")

        def stop(self):
            pass
