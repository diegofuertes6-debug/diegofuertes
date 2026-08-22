"""Android integrations loaded safely on desktop.

All Android and Java imports are intentionally lazy so importing this module
never requires pyjnius or python-for-android outside an APK.
"""

import os


LOCATION_PERMISSIONS = (
    'android.permission.ACCESS_COARSE_LOCATION',
    'android.permission.ACCESS_FINE_LOCATION',
)
MICROPHONE_PERMISSIONS = ('android.permission.RECORD_AUDIO',)

SPEECH_REQUEST_CODE = 4107

_speech_callback = None
_location_cancel = None


def is_android():
    try:
        from kivy.utils import platform

        platform_name = platform() if callable(platform) else platform
    except ImportError:
        platform_name = ''
    return str(platform_name).lower() == 'android' or bool(os.environ.get('ANDROID_ARGUMENT'))


def denied_permissions(permissions, grants):
    """Return denied permission names from Android's callback values."""
    return [
        permission
        for index, permission in enumerate(permissions)
        if index >= len(grants) or not bool(grants[index])
    ]


def has_location_permission(denied):
    """Return true when coarse or fine location remains available."""
    denied = set(denied)
    return any(permission not in denied for permission in LOCATION_PERMISSIONS)


def location_permission_granted():
    """Return whether coarse or fine location is currently granted."""
    if not is_android():
        return True
    try:
        from android.permissions import check_permission

        return any(check_permission(permission) for permission in LOCATION_PERMISSIONS)
    except (ImportError, AttributeError):
        return False


def is_location_enabled():
    """Return whether Android has at least one usable location provider."""
    if not is_android():
        return True

    try:
        from android import mActivity
        from jnius import autoclass

        Context = autoclass('android.content.Context')
        BuildVersion = autoclass('android.os.Build$VERSION')
        LocationManager = autoclass('android.location.LocationManager')
        manager = mActivity.getSystemService(Context.LOCATION_SERVICE)
        if manager is None:
            return False
        if BuildVersion.SDK_INT >= 28:
            return bool(manager.isLocationEnabled())
        return bool(
            manager.isProviderEnabled(LocationManager.GPS_PROVIDER)
            or manager.isProviderEnabled(LocationManager.NETWORK_PROVIDER)
        )
    except Exception:
        return False


def open_location_settings(on_error):
    """Open Android's location-source panel so the user can enable providers."""
    if not is_android():
        on_error('Los ajustes de ubicación solo están disponibles en Android.')
        return False
    try:
        from android import mActivity
        from jnius import autoclass

        Intent = autoclass('android.content.Intent')
        Settings = autoclass('android.provider.Settings')
        mActivity.startActivity(Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS))
        return True
    except Exception as exc:
        on_error(f'No se pudieron abrir los ajustes de ubicación: {exc}')
        return False


def open_map_url(url, on_error):
    """Open a Maps directions URL through Android's ACTION_VIEW intent."""
    if not is_android():
        on_error('La aplicación de mapas solo se abre por Intent en Android.')
        return False
    try:
        from android import mActivity
        from jnius import autoclass

        Intent = autoclass('android.content.Intent')
        Uri = autoclass('android.net.Uri')
        intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
        intent.setPackage('com.google.android.apps.maps')
        if intent.resolveActivity(mActivity.getPackageManager()) is None:
            intent.setPackage(None)
        if intent.resolveActivity(mActivity.getPackageManager()) is None:
            on_error('No hay ninguna aplicación de mapas disponible.')
            return False
        mActivity.startActivity(intent)
        return True
    except Exception as exc:
        on_error(f'No se pudo abrir la ruta en el mapa: {exc}')
        return False


def request_runtime_permissions(permissions, callback):
    """Request only missing permissions and report ``(granted, denied)``."""
    permissions = tuple(permissions)
    if not is_android():
        callback(True, [])
        return

    try:
        from android.permissions import check_permission, request_permissions
    except (ImportError, AttributeError):
        callback(False, list(permissions))
        return

    try:
        missing = [
            permission
            for permission in permissions
            if not check_permission(permission)
        ]
        if not missing:
            callback(True, [])
            return

        def on_permissions_result(_requested, _grants):
            denied = [
                permission
                for permission in missing
                if not check_permission(permission)
            ]
            callback(not denied, denied)

        request_permissions(missing, on_permissions_result)
    except Exception:
        callback(False, list(permissions))


def get_current_location(on_location, on_error):
    """Request a single GPS fix and stop listening immediately afterward."""
    global _location_cancel

    if is_android() and not is_location_enabled():
        on_error(
            'La ubicación del dispositivo está desactivada. '
            'Actívala en Ajustes y vuelve a intentarlo.'
        )
        return None

    try:
        from plyer import gps
    except (ImportError, AttributeError):
        on_error('El servicio de ubicación no está disponible en este dispositivo.')
        return None

    from kivy.clock import Clock

    completed = {'value': False}
    timeout_event = {'value': None}

    def stop():
        global _location_cancel
        completed['value'] = True
        event = timeout_event['value']
        if event is not None:
            event.cancel()
        try:
            gps.stop()
        except Exception:
            pass
        if _location_cancel is stop:
            _location_cancel = None

    def timeout(_delta):
        if completed['value']:
            return
        completed['value'] = True
        stop()
        _dispatch(
            on_error,
            'No se obtuvo una ubicación en 15 segundos. Sal a una zona abierta '
            'y vuelve a abrir la ruta para reintentar.',
        )

    def finish_location(**location):
        if completed['value']:
            return
        latitude = location.get('lat')
        longitude = location.get('lon', location.get('lng'))
        if latitude is None or longitude is None:
            return
        completed['value'] = True
        stop()
        _dispatch(on_location, {'lat': float(latitude), 'lng': float(longitude)})

    def report_status(status_type, status_message):
        if completed['value']:
            return
        if str(status_type).lower() in {'provider-disabled', 'gps-disabled'}:
            completed['value'] = True
            stop()
            _dispatch(
                on_error,
                'Activa la ubicación del dispositivo para obtener tu posición actual.'
            )

    try:
        gps.configure(on_location=finish_location, on_status=report_status)
        gps.start(minTime=1000, minDistance=0)
        timeout_event['value'] = Clock.schedule_once(timeout, 15)
        _location_cancel = stop
        return stop
    except Exception as exc:
        stop()
        _dispatch(on_error, f'No se pudo iniciar la ubicación: {exc}')
        return None


def cancel_location_request():
    """Cancel the active one-shot location request, if any."""
    cancel = _location_cancel
    if cancel is not None:
        cancel()


def start_speech_recognition(on_success, on_error):
    """Launch Android speech recognition and return its first result."""
    global _speech_callback

    if _speech_callback is not None:
        on_error('Ya hay un reconocimiento de voz en curso.')
        return

    try:
        from android import activity
        from android import mActivity
        from jnius import autoclass

        Intent = autoclass('android.content.Intent')
        RecognizerIntent = autoclass('android.speech.RecognizerIntent')
        intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
        intent.putExtra(
            RecognizerIntent.EXTRA_LANGUAGE_MODEL,
            RecognizerIntent.LANGUAGE_MODEL_FREE_FORM,
        )
        intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, 'es-ES')
        intent.putExtra(
            RecognizerIntent.EXTRA_PROMPT,
            'Di la dirección completa',
        )

        def on_activity_result(request_code, result_code, data):
            global _speech_callback
            if request_code != SPEECH_REQUEST_CODE:
                return
            activity.unbind(on_activity_result=on_activity_result)
            _speech_callback = None
            if result_code != -1 or data is None:
                _dispatch(on_error, 'No se recibió ninguna dirección por voz.')
                return
            results = data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
            if results is None or results.size() == 0:
                _dispatch(on_error, 'No se reconoció ninguna dirección.')
                return
            texto = str(results.get(0)).strip()
            if not texto:
                _dispatch(on_error, 'No se reconoció ninguna dirección.')
                return
            _dispatch(on_success, texto)

        _speech_callback = on_activity_result
        activity.bind(on_activity_result=on_activity_result)
        mActivity.startActivityForResult(intent, SPEECH_REQUEST_CODE)
    except Exception as exc:
        try:
            activity.unbind(on_activity_result=_speech_callback)
        except Exception:
            pass
        _speech_callback = None
        _dispatch(on_error, f'El reconocimiento de voz no está disponible: {exc}')


def cancel_pending_activities():
    """Unbind pending Android result listeners when the app is stopping."""
    global _speech_callback
    if not is_android():
        _speech_callback = None
        return
    try:
        from android import activity

        if _speech_callback is not None:
            activity.unbind(on_activity_result=_speech_callback)
    except (ImportError, AttributeError):
        pass
    finally:
        _speech_callback = None
        cancel_location_request()


def _dispatch(callback, *args):
    """Run Java worker callbacks on Kivy's UI thread."""
    try:
        from kivy.clock import Clock

        Clock.schedule_once(lambda _delta: callback(*args), 0)
    except ImportError:
        callback(*args)
