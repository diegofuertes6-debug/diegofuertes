"""Android integrations loaded safely on desktop.

All Android and Java imports are intentionally lazy so importing this module
never requires pyjnius or python-for-android outside an APK.
"""

import os


LOCATION_PERMISSIONS = (
    'android.permission.ACCESS_COARSE_LOCATION',
    'android.permission.ACCESS_FINE_LOCATION',
)
CAMERA_PERMISSIONS = ('android.permission.CAMERA',)
MICROPHONE_PERMISSIONS = ('android.permission.RECORD_AUDIO',)

SPEECH_REQUEST_CODE = 4107
CAMERA_REQUEST_CODE = 4108

_listener_refs = []
_speech_callback = None
_camera_callback = None


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


def capture_photo(filename, on_complete, on_error):
    """Open the native camera and save one temporary image."""
    global _camera_callback

    if not is_android():
        try:
            from plyer import camera

            camera.take_picture(filename=filename, on_complete=on_complete)
        except Exception as exc:
            on_error(f'No se pudo abrir la cámara: {exc}')
        return

    try:
        from android import activity
        from android import mActivity
        from jnius import autoclass, cast

        Intent = autoclass('android.content.Intent')
        MediaStore = autoclass('android.provider.MediaStore')
        BuildVersion = autoclass('android.os.Build$VERSION')
        output_uri = None

        if BuildVersion.SDK_INT >= 29:
            ContentValues = autoclass('android.content.ContentValues')
            Environment = autoclass('android.os.Environment')
            values = ContentValues()
            values.put(MediaStore.Images.Media.DISPLAY_NAME, 'direccion_temporal.jpg')
            values.put(MediaStore.Images.Media.MIME_TYPE, 'image/jpeg')
            values.put(
                MediaStore.Images.Media.RELATIVE_PATH,
                f'{Environment.DIRECTORY_PICTURES}/Repartidor',
            )
            values.put(MediaStore.Images.Media.IS_PENDING, 1)
            output_uri = mActivity.getContentResolver().insert(
                MediaStore.Images.Media.EXTERNAL_CONTENT_URI,
                values,
            )
            if output_uri is None:
                raise OSError('no se pudo reservar la captura temporal')

        def on_activity_result(request_code, result_code, data):
            global _camera_callback
            if request_code != CAMERA_REQUEST_CODE:
                return
            activity.unbind(on_activity_result=on_activity_result)
            _camera_callback = None
            if result_code != -1:
                _delete_media_uri(mActivity, output_uri)
                on_error('No se capturó ninguna imagen.')
                return
            try:
                if output_uri is not None:
                    _copy_media_to_private_file(mActivity, output_uri, filename)
                else:
                    _save_camera_thumbnail(data, filename)
                if os.path.isfile(filename) and os.path.getsize(filename) > 0:
                    on_complete(filename)
                else:
                    on_error('La cámara no devolvió una imagen válida.')
            except Exception as exc:
                on_error(f'No se pudo guardar la captura: {exc}')
            finally:
                _delete_media_uri(mActivity, output_uri)

        _camera_callback = on_activity_result
        activity.bind(on_activity_result=on_activity_result)
        intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
        if output_uri is not None:
            intent.putExtra(
                MediaStore.EXTRA_OUTPUT,
                cast('android.os.Parcelable', output_uri),
            )
            intent.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
            intent.addFlags(Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
        activity.startActivityForResult(intent, CAMERA_REQUEST_CODE)
    except Exception as exc:
        try:
            activity.unbind(on_activity_result=_camera_callback)
        except Exception:
            pass
        try:
            _delete_media_uri(mActivity, output_uri)
        except NameError:
            pass
        _camera_callback = None
        on_error(f'No se pudo abrir la cámara: {exc}')


def _copy_media_to_private_file(activity, uri, filename):
    from jnius import autoclass

    FileOutputStream = autoclass('java.io.FileOutputStream')
    FileUtils = autoclass('android.os.FileUtils')
    input_stream = activity.getContentResolver().openInputStream(uri)
    if input_stream is None:
        raise OSError('no se pudo leer la captura temporal')
    output_stream = FileOutputStream(filename)
    try:
        FileUtils.copy(input_stream, output_stream)
        output_stream.flush()
    finally:
        input_stream.close()
        output_stream.close()


def _save_camera_thumbnail(data, filename):
    from jnius import autoclass, cast

    if data is None or data.getExtras() is None:
        raise ValueError('la cámara no devolvió una imagen')
    Bitmap = autoclass('android.graphics.Bitmap')
    FileOutputStream = autoclass('java.io.FileOutputStream')
    bitmap = cast('android.graphics.Bitmap', data.getExtras().get('data'))
    if bitmap is None:
        raise ValueError('la cámara no devolvió una imagen')
    output_stream = FileOutputStream(filename)
    try:
        if not bitmap.compress(Bitmap.CompressFormat.JPEG, 95, output_stream):
            raise OSError('no se pudo guardar la imagen temporal')
        output_stream.flush()
    finally:
        output_stream.close()


def _delete_media_uri(activity, uri):
    if uri is not None:
        try:
            activity.getContentResolver().delete(uri, None, None)
        except Exception as exc:
            print(f'No se pudo eliminar la captura temporal de MediaStore: {exc}')


def recognize_image_text(filename, on_success, on_error):
    """Run on-device ML Kit OCR for a captured image."""
    if not is_android():
        on_error('El OCR Android solo está disponible dentro de la aplicación móvil.')
        return

    try:
        from android import mActivity
        from jnius import PythonJavaClass, autoclass, cast, java_method

        InputImage = autoclass('com.google.mlkit.vision.common.InputImage')
        TextRecognition = autoclass('com.google.mlkit.vision.text.TextRecognition')
        TextRecognizerOptions = autoclass(
            'com.google.mlkit.vision.text.latin.TextRecognizerOptions'
        )
        Uri = autoclass('android.net.Uri')
        File = autoclass('java.io.File')

        image = InputImage.fromFilePath(mActivity, Uri.fromFile(File(filename)))
        recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)

        operation_refs = []

        def release_operation():
            for reference in operation_refs:
                if reference in _listener_refs:
                    _listener_refs.remove(reference)
            recognizer.close()

        class SuccessListener(PythonJavaClass):
            __javainterfaces__ = ['com/google/android/gms/tasks/OnSuccessListener']
            __javacontext__ = 'app'

            @java_method('(Ljava/lang/Object;)V')
            def onSuccess(self, result):
                try:
                    text_result = cast('com.google.mlkit.vision.text.Text', result)
                    _dispatch(on_success, str(text_result.getText() or ''))
                finally:
                    release_operation()

        class FailureListener(PythonJavaClass):
            __javainterfaces__ = ['com/google/android/gms/tasks/OnFailureListener']
            __javacontext__ = 'app'

            @java_method('(Ljava/lang/Exception;)V')
            def onFailure(self, exception):
                try:
                    _dispatch(on_error, f'No se pudo analizar la imagen: {exception}')
                finally:
                    release_operation()

        success_listener = SuccessListener()
        failure_listener = FailureListener()
        operation_refs.extend([success_listener, failure_listener, recognizer])
        _listener_refs.extend(operation_refs)
        recognizer.process(image).addOnSuccessListener(
            success_listener
        ).addOnFailureListener(failure_listener)
    except Exception as exc:
        on_error(f'No se pudo iniciar el OCR: {exc}')

def get_current_location(on_location, on_error):
    """Request a single GPS fix and stop listening immediately afterward."""
    try:
        from plyer import gps
    except (ImportError, AttributeError):
        on_error('El servicio de ubicación no está disponible en este dispositivo.')
        return

    from kivy.clock import Clock

    completed = {'value': False}
    timeout_event = {'value': None}

    def stop():
        event = timeout_event['value']
        if event is not None:
            event.cancel()
        try:
            gps.stop()
        except Exception:
            pass

    def timeout(_delta):
        if completed['value']:
            return
        completed['value'] = True
        stop()
        on_error('No se obtuvo una ubicación. Comprueba que el GPS esté activo.')

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
    except Exception as exc:
        stop()
        _dispatch(on_error, f'No se pudo iniciar la ubicación: {exc}')


def start_speech_recognition(on_success, on_error):
    """Launch Android speech recognition and return its first result."""
    global _speech_callback

    try:
        from android import activity
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
                on_error('No se recibió ninguna dirección por voz.')
                return
            results = data.getStringArrayListExtra(RecognizerIntent.EXTRA_RESULTS)
            if results is None or results.size() == 0:
                on_error('No se reconoció ninguna dirección.')
                return
            on_success(str(results.get(0)).strip())

        _speech_callback = on_activity_result
        activity.bind(on_activity_result=on_activity_result)
        activity.startActivityForResult(intent, SPEECH_REQUEST_CODE)
    except Exception as exc:
        try:
            activity.unbind(on_activity_result=_speech_callback)
        except Exception:
            pass
        _speech_callback = None
        on_error(f'El reconocimiento de voz no está disponible: {exc}')


def _dispatch(callback, *args):
    """Run Java worker callbacks on Kivy's UI thread."""
    try:
        from kivy.clock import Clock

        Clock.schedule_once(lambda _delta: callback(*args), 0)
    except ImportError:
        callback(*args)
