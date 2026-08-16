# -*- coding: utf-8 -*-
"""Aplicación de reparto robusta para escritorio y Android.

Geolocalización, gestión de paradas con prioridad y optimización de rutas.

Cómo funciona la regla de las 19:00
-------------------------------------
- La hora local del dispositivo se consulta con ``datetime.now().hour``.
- Si la hora actual es >= 19, ``priorizar_paradas`` reordena primero por
  prioridad (alta > media > baja) y dentro de cada grupo conserva el orden
  de menor distancia acumulada (nearest-neighbor greedy).
- Si la app se abre después de las 19:00 la política se aplica desde el
  primer cálculo. El recálculo también ocurre cuando el usuario añade o
  elimina paradas o cambia el modo de transporte.

Modos de transporte reconocidos: ``'pie'``, ``'coche'``, ``'moto'``.
"""
import json
import os
import re
from datetime import datetime
import math
from urllib.parse import quote

DEFAULT_PHOTO_FILENAME = 'foto_direccion.jpg'
API_KEY_ENV_VAR = 'GOOGLE_MAPS_API_KEY'
API_KEY_CANDIDATES = (
    API_KEY_ENV_VAR,
    'googleMapsApiKey',
    'google_maps_api_key',
    'api_key',
    'apiKey',
    'key',
)
PRIORITY_ORDER = ('alta', 'media', 'baja')
PRIORITY_COLORS = {
    'alta': (1.0, 0.0, 0.0, 1.0),
    'media': (1.0, 1.0, 0.0, 1.0),
    'baja': (0.0, 1.0, 0.0, 1.0),
}
TRANSPORT_SPEEDS_KMH = {'pie': 5.0, 'coche': 35.0, 'moto': 30.0}
CAPTURE_METHODS = {
    'cámara': 'camara',
    'camara': 'camara',
    'micrófono': 'microfono',
    'microfono': 'microfono',
    'voz': 'microfono',
    'búsqueda': 'manual',
    'busqueda': 'manual',
    'entrada': 'manual',
    'manual': 'manual',
}
_PREFIJO_DIRECCION_RE = re.compile(
    r'\b(?:Calle|Calleja|C/|C\./|Avda\.?|Avenida|Avinguda|Plaza|'
    r'Paseo|Carrera|Camino|Ronda|V[ií]a|Carretera|Traves[ií]a)(?=\s|$)',
    re.IGNORECASE,
)
_CODIGO_POSTAL_RE = re.compile(r'\b\d{5}\b')
_NUMERO_PORTAL_RE = re.compile(r'\b\d{1,4}[A-Za-z]?(?:[-/]\d{1,4}[A-Za-z]?)?\b')

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import requests
except ImportError:
    requests = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    from kivy.utils import platform as kivy_platform
except ImportError:
    kivy_platform = None


def _get_platform_name():
    if callable(kivy_platform):
        try:
            return str(kivy_platform()).lower()
        except Exception:
            return ''
    return str(kivy_platform or '').lower()


def _safe_read_json(path):
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding='utf-8') as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return None


def _resolve_path(path):
    if not path:
        path = DEFAULT_PHOTO_FILENAME
    path = os.path.expanduser(str(path))
    if os.path.isabs(path):
        return path
    return os.path.abspath(os.path.join(os.path.dirname(__file__), path))


def _is_android():
    return _get_platform_name() == 'android' or os.environ.get('ANDROID_ARGUMENT') is not None


def take_photo(filename='foto_direccion.jpg', quality=0.8):
    del quality
    target_path = _resolve_path(filename)
    if os.path.exists(target_path):
        return target_path

    if _is_android():
        print(
            'La captura Android es asíncrona; usa '
            'android_services.capture_photo desde la interfaz.'
        )
        return target_path

    try:
        import cv2
    except ImportError:
        cv2 = None

    if cv2 is not None:
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            ok, frame = cap.read()
            if ok and frame is not None:
                cv2.imwrite(target_path, frame)
                cap.release()
                if os.path.exists(target_path):
                    return target_path
            cap.release()

    print('No se pudo capturar una foto automáticamente; se usará la ruta indicada.')
    return target_path


def procesar_imagen(path):
    texto = leer_texto_imagen(path)
    return extraer_direccion_texto_ocr(texto)


def leer_texto_imagen(path):
    """Extract all OCR text from an image on desktop."""
    target_path = _resolve_path(path)
    if not os.path.isfile(target_path):
        print(f'No existe la imagen: {target_path}')
        return ''

    if pytesseract is None or Image is None:
        print('pytesseract/Pillow no están disponibles para procesar la imagen.')
        return ''

    try:
        with Image.open(target_path) as image:
            return str(pytesseract.image_to_string(image, lang='eng+spa') or '')
    except (OSError, ValueError) as exc:
        print(f'No se pudo procesar la imagen: {exc}')
        return ''


def extraer_direccion_texto_ocr(texto):
    """Extract a likely Spanish street address and postal code from OCR text."""
    componentes = extraer_componentes_direccion_ocr(texto)
    if componentes:
        direccion = componentes.get('calle', '')
        if componentes.get('numero'):
            direccion = f'{direccion} {componentes["numero"]}'.strip()
        return direccion, componentes.get('codigo_postal', '')
    candidatos = extraer_candidatos_direccion_ocr(texto)
    if not candidatos:
        return '', ''
    direccion = candidatos[0]
    cp_match = _CODIGO_POSTAL_RE.search(direccion)
    cp_final = cp_match.group() if cp_match else ''
    if cp_final:
        direccion = re.sub(rf'(?:,\s*)?\b{re.escape(cp_final)}\b.*$', '', direccion).strip(' ,')
    return direccion, cp_final


def normalizar_direccion(texto):
    """Normalize user-provided address text without changing its meaning."""
    texto = re.sub(r'[\r\n\t]+', ' ', str(texto or ''))
    texto = re.sub(r'\s+', ' ', texto).strip(' ,;')
    return texto


def _normalizar_metodo_captura(origen):
    origen = normalizar_direccion(origen).casefold()
    return CAPTURE_METHODS.get(origen, 'manual')


def _extraer_componentes_direccion(candidato):
    candidato = normalizar_direccion(candidato)
    if not candidato:
        return {}

    prefijo = _PREFIJO_DIRECCION_RE.match(candidato)
    if prefijo is None:
        return {}

    cp_match = _CODIGO_POSTAL_RE.search(candidato)
    if cp_match is None:
        return {}

    tipo_via = normalizar_direccion(prefijo.group(0))
    tramo_pre_cp = normalizar_direccion(candidato[:cp_match.start()])
    tramo_post_cp = normalizar_direccion(candidato[cp_match.end():].strip(' ,'))
    sin_prefijo = normalizar_direccion(tramo_pre_cp[prefijo.end():])

    numero = ''
    numero_match = _NUMERO_PORTAL_RE.search(sin_prefijo)
    if numero_match is not None:
        numero = numero_match.group(0)
        nombre_calle = normalizar_direccion(
            f'{sin_prefijo[:numero_match.start()]} {sin_prefijo[numero_match.end():]}'
        )
    else:
        nombre_calle = sin_prefijo

    calle = normalizar_direccion(f'{tipo_via} {nombre_calle}')
    poblacion = normalizar_direccion(tramo_post_cp)
    codigo_postal = cp_match.group(0)

    direccion = calle
    if numero:
        direccion = f'{direccion} {numero}'.strip()
    if codigo_postal or poblacion:
        direccion = f'{direccion}, {normalizar_direccion(f"{codigo_postal} {poblacion}")}'.strip(', ')

    return {
        'calle': calle,
        'nombre_calle': nombre_calle,
        'numero': numero,
        'codigo_postal': codigo_postal,
        'poblacion': poblacion,
        'address': normalizar_direccion(direccion),
    }


def extraer_componentes_direccion_ocr(texto):
    """Return structured OCR address parts for the most plausible candidate."""
    candidatos = extraer_candidatos_direccion_ocr(texto)
    if not candidatos:
        return {}
    return _extraer_componentes_direccion(candidatos[0])


def extraer_candidatos_direccion_ocr(texto):
    """Return plausible address lines ordered by confidence, without OCR noise."""
    texto = str(texto or '').replace('\r', '\n')
    if not texto.strip():
        return []
    lineas = [normalizar_direccion(linea) for linea in texto.split('\n')]
    candidatos = []
    for indice, linea in enumerate(lineas):
        coincidencia = _PREFIJO_DIRECCION_RE.search(linea) if linea else None
        if coincidencia is None:
            continue
        fragmentos = [linea[coincidencia.start():]]
        for siguiente in lineas[indice + 1:indice + 5]:
            if not siguiente:
                continue
            es_numero_portal = bool(
                re.fullmatch(r'\d{1,4}[A-Za-z]?(?:[-/]\d{1,4}[A-Za-z]?)?', siguiente)
            )
            parece_poblacion = bool(
                re.fullmatch(r'[A-Za-zÁÉÍÓÚÜÑáéíóúüñ.\- ]{2,40}', siguiente)
            )
            if (
                len(fragmentos[-1]) <= 16
                and not es_numero_portal
                and not _CODIGO_POSTAL_RE.search(siguiente)
                and not _PREFIJO_DIRECCION_RE.search(siguiente)
            ):
                fragmentos[-1] = normalizar_direccion(f'{fragmentos[-1]} {siguiente}')
                continue
            if es_numero_portal or (
                _CODIGO_POSTAL_RE.search(siguiente) and len(siguiente) <= 60
            ) or (
                parece_poblacion and any(_CODIGO_POSTAL_RE.search(parte) for parte in fragmentos)
            ):
                fragmentos.append(siguiente)
            if _CODIGO_POSTAL_RE.search(siguiente) and ',' in siguiente:
                break
            if (
                parece_poblacion
                and any(_CODIGO_POSTAL_RE.search(parte) for parte in fragmentos)
            ):
                break
        candidato = normalizar_direccion(', '.join(fragmentos))
        componentes = _extraer_componentes_direccion(candidato)
        if componentes.get('address'):
            candidato = componentes['address']
        if len(candidato) >= 6 and candidato.casefold() not in {
            existente.casefold() for existente in candidatos
        }:
            candidatos.append(candidato)

    return sorted(
        candidatos,
        key=lambda candidato: (
            not bool(re.search(r'\d', candidato)),
            not bool(_CODIGO_POSTAL_RE.search(candidato)),
            len(candidato),
        ),
    )


def cargar_api_key():
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env')

    if load_dotenv is not None and os.path.exists(dotenv_path):
        try:
            load_dotenv(dotenv_path=dotenv_path, override=False)
        except Exception as exc:
            print(f'No se pudo cargar .env: {exc}')
    elif os.path.exists(dotenv_path):
        with open(dotenv_path, encoding='utf-8') as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key == API_KEY_ENV_VAR and value and value != 'TU_API_KEY_AQUÍ':
                    return value

    api_key = os.getenv(API_KEY_ENV_VAR, '').strip()
    if api_key and api_key != 'TU_API_KEY_AQUÍ':
        return api_key

    settings_path = os.path.join(os.path.dirname(__file__), 'webServerApiSettings.json')
    data = _safe_read_json(settings_path)
    if isinstance(data, dict):
        for key in API_KEY_CANDIDATES:
            value = data.get(key)
            if isinstance(value, str) and value.strip() and value.strip() != 'TU_API_KEY_AQUÍ':
                return value.strip()

    return ''


API_KEY = cargar_api_key()

lista_paradas = []


def obtener_coordenadas(direccion, cp):
    if not direccion or not cp:
        return None

    if requests is None:
        print('requests no está instalado; se omite la geolocalización.')
        return None

    if not API_KEY:
        print('No hay API key configurada; se omite la geocodificación.')
        return None

    full_address = f'{direccion}, {cp}, España'
    url = 'https://maps.googleapis.com/maps/api/geocode/json'
    params = {'address': full_address, 'key': API_KEY}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        res = resp.json()
    except requests.RequestException as exc:
        print(f'Error al solicitar geocodificación: {exc}')
        return None
    except ValueError as exc:
        print(f'Respuesta inválida de geocodificación: {exc}')
        return None

    if res.get('status') == 'OK' and res.get('results'):
        loc = res['results'][0]['geometry']['location']
        return {'lat': loc['lat'], 'lng': loc['lng'], 'address': full_address, 'prioridad': 'media', 'estado': 'pendiente'}
    return None


def asignar_prioridad(parada, prioridad):
    if not isinstance(parada, dict):
        return parada
    prioridad_valida = prioridad.lower().strip() if isinstance(prioridad, str) else 'media'
    if prioridad_valida not in PRIORITY_ORDER:
        prioridad_valida = 'media'
    parada['prioridad'] = prioridad_valida
    return parada


def _clave_direccion(texto):
    texto = normalizar_direccion(texto).casefold()
    return re.sub(r'[^\w]+', '', texto, flags=re.UNICODE)


def validar_y_anadir_parada(
    paradas,
    texto,
    geocodificador=None,
    prioridad='media',
    paqueteria=None,
    notificacion=None,
    origen='manual',
):
    """Validate, geocode and append a stop through one consistent operation.

    Returns ``(parada, error)``. Exactly one value is non-``None``.
    """
    if not isinstance(paradas, list):
        return None, 'No se pudo acceder al listado de paradas.'

    direccion = normalizar_direccion(texto)
    if len(direccion) < 5 or not re.search(r'[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]', direccion):
        return None, 'Introduce una dirección válida antes de añadirla.'

    clave_entrada = _clave_direccion(direccion)
    for existente in paradas:
        if isinstance(existente, dict) and _clave_direccion(existente.get('address')) == clave_entrada:
            return None, 'Esa dirección ya está en el listado.'

    geocodificador = geocodificador or buscar_direccion_texto
    parada = geocodificador(direccion)
    if not isinstance(parada, dict) or not coordenadas_validas(
        parada.get('lat'), parada.get('lng')
    ):
        return None, (
            'No se obtuvieron coordenadas para esa dirección. Comprueba la '
            'dirección, la conexión y la API key.'
        )

    direccion_resuelta = normalizar_direccion(parada.get('address') or direccion)
    clave_resuelta = _clave_direccion(direccion_resuelta)
    for existente in paradas:
        if isinstance(existente, dict) and _clave_direccion(existente.get('address')) == clave_resuelta:
            return None, 'Esa dirección ya está en el listado.'

    parada['address'] = direccion_resuelta
    parada['nombre'] = parada.get('nombre') or direccion
    parada['numero'] = parada.get('numero') or (len(paradas) + 1)
    parada['estado'] = parada.get('estado') or 'pendiente'
    asignar_prioridad(parada, prioridad)
    parada['paqueteria'] = paqueteria or parada.get('paqueteria') or ''
    parada['notificacion'] = notificacion or parada.get('notificacion') or ''
    parada['metodo_captura'] = parada.get('metodo_captura') or _normalizar_metodo_captura(origen)
    paradas.append(parada)
    return parada, None


def iniciar_alta_parada(
    paradas,
    texto,
    origen='entrada',
    prioridad='media',
    paqueteria=None,
    notificacion=None,
):
    """Append one provisional stop that is not routable until geocoding succeeds."""
    if not isinstance(paradas, list):
        return None, 'No se pudo acceder al listado de paradas.'
    direccion = normalizar_direccion(texto)
    if len(direccion) < 5 or not re.search(r'[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]', direccion):
        return None, 'Introduce una dirección válida antes de añadirla.'
    clave = _clave_direccion(direccion)
    if any(
        isinstance(parada, dict)
        and _clave_direccion(parada.get('address')) == clave
        for parada in paradas
    ):
        return None, 'Esa dirección ya está en el listado.'

    parada = {
        'address': direccion,
        'nombre': direccion,
        'numero': len(paradas) + 1,
        'estado': 'geolocalizando',
        'origen': origen,
        'paqueteria': paqueteria or '',
        'notificacion': notificacion or '',
        'metodo_captura': _normalizar_metodo_captura(origen),
    }
    asignar_prioridad(parada, prioridad)
    paradas.append(parada)
    return parada, None


def resolver_geocodificacion(texto, geocodificador=None):
    """Run only the potentially blocking geocoder, without mutating UI state."""
    geocodificador = geocodificador or buscar_direccion_texto
    direccion = normalizar_direccion(texto)
    try:
        resultado = geocodificador(direccion)
    except Exception as exc:
        resultado = None
        detalle = str(exc).strip()
    else:
        detalle = ''
    return resultado, detalle


def aplicar_alta_geocodificada(paradas, parada, resultado, detalle=''):
    """Apply one geocoder result atomically to a provisional stop."""
    if not isinstance(parada, dict) or parada not in paradas:
        return None, 'La parada ya no está disponible.'
    direccion = normalizar_direccion(parada.get('address'))

    if not isinstance(resultado, dict) or not coordenadas_validas(
        resultado.get('lat') if isinstance(resultado, dict) else None,
        resultado.get('lng') if isinstance(resultado, dict) else None,
    ):
        parada.pop('lat', None)
        parada.pop('lng', None)
        parada['estado'] = 'error'
        parada['error'] = (
            'No se obtuvieron coordenadas. Comprueba la dirección, la conexión '
            'y la API key.'
        )
        if detalle:
            parada['error'] += f' Detalle: {detalle}'
        return None, parada['error']

    direccion_resuelta = normalizar_direccion(resultado.get('address') or direccion)
    clave_resuelta = _clave_direccion(direccion_resuelta)
    if any(
        existente is not parada
        and isinstance(existente, dict)
        and _clave_direccion(existente.get('address')) == clave_resuelta
        for existente in paradas
    ):
        parada['estado'] = 'error'
        parada['error'] = 'La dirección geolocalizada ya está en el listado.'
        return None, parada['error']

    parada['lat'] = resultado['lat']
    parada['lng'] = resultado['lng']
    parada['address'] = direccion_resuelta
    parada['nombre'] = parada.get('nombre') or direccion
    parada['numero'] = parada.get('numero') or (paradas.index(parada) + 1)
    parada['estado'] = 'geolocalizada'
    parada.pop('error', None)
    return parada, None


def completar_alta_parada(paradas, parada, geocodificador=None):
    """Resolve and apply a provisional stop synchronously for compatibility."""
    resultado, detalle = resolver_geocodificacion(
        parada.get('address') if isinstance(parada, dict) else '',
        geocodificador,
    )
    return aplicar_alta_geocodificada(paradas, parada, resultado, detalle)


def _haversine(lat1, lng1, lat2, lng2):
    """Distancia en km entre dos puntos (fórmula haversine)."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def coordenadas_validas(lat, lng):
    """Return whether latitude and longitude form a real geographic point."""
    if (
        isinstance(lat, bool)
        or isinstance(lng, bool)
        or not isinstance(lat, (int, float))
        or not isinstance(lng, (int, float))
    ):
        return False
    return (
        math.isfinite(lat)
        and math.isfinite(lng)
        and -90 <= lat <= 90
        and -180 <= lng <= 180
    )


def _nearest_neighbor(paradas, origen_lat=None, origen_lng=None):
    """Ordena *paradas* con la heurística del vecino más cercano.

    Si no se dispone de coordenadas válidas en una parada se mantiene su
    posición relativa.  El punto de inicio puede ser la posición actual del
    repartidor (``origen_lat``/``origen_lng``) o, si es ``None``, el primer
    elemento de la lista.
    """
    candidatos = [
        p for p in paradas
        if coordenadas_validas(p.get('lat'), p.get('lng'))
    ]
    sin_coords = [p for p in paradas if p not in candidatos]

    if not candidatos:
        return list(paradas)

    if origen_lat is None or origen_lng is None:
        cur_lat = candidatos[0]['lat']
        cur_lng = candidatos[0]['lng']
        pendientes = candidatos[1:]
        ruta = [candidatos[0]]
    else:
        cur_lat, cur_lng = origen_lat, origen_lng
        pendientes = list(candidatos)
        ruta = []

    while pendientes:
        mas_cercana = min(pendientes, key=lambda p: _haversine(cur_lat, cur_lng, p['lat'], p['lng']))
        ruta.append(mas_cercana)
        pendientes.remove(mas_cercana)
        cur_lat, cur_lng = mas_cercana['lat'], mas_cercana['lng']

    return ruta + sin_coords


# ---------------------------------------------------------------------------
# Geolocalización del repartidor
# ---------------------------------------------------------------------------

def solicitar_permiso_geolocalizacion():
    """Solicita el permiso de localización en Android.

    En plataformas no-Android (escritorio / tests) devuelve ``True``
    directamente sin solicitar nada.

    Returns:
        bool: ``True`` si el permiso fue concedido o no se necesita solicitar,
              ``False`` si el permiso fue denegado.
    """
    if not _is_android():
        return True

    try:
        from android.permissions import (
            Permission,
            check_permission,
            request_permissions,
        )

        perm = Permission.ACCESS_FINE_LOCATION
        if check_permission(perm):
            return True
        request_permissions([perm])
        return check_permission(perm)
    except (ImportError, AttributeError) as exc:
        print(f'No se pudo solicitar permiso de geolocalización: {exc}')
        return False


def obtener_ubicacion_actual():
    """Devuelve la ubicación GPS actual como ``{'lat': float, 'lng': float}`` o ``None``.

    En Android usa ``plyer.gps``; en escritorio usa ``requests`` contra la
    API de geolocalización de Google si hay API key, y como último recurso
    devuelve ``None``.

    El permiso de geolocalización debe estar concedido antes de llamar a
    esta función (ver ``solicitar_permiso_geolocalizacion``).
    """
    if _is_android():
        try:
            from plyer import gps

            gps.configure(on_location=lambda **_: None, on_status=lambda *_: None)
            gps.start(minTime=0, minDistance=0)
            import time
            time.sleep(1)
            provider = gps.location
            if provider and provider.get('lat') is not None:
                return {'lat': provider['lat'], 'lng': provider['lon']}
        except Exception as exc:
            print(f'No se pudo obtener la ubicación en Android: {exc}')
        return None

    # Escritorio: intentar geolocalización por IP (sin permiso necesario)
    if requests is None:
        return None
    try:
        resp = requests.get('https://ipapi.co/json/', timeout=5)
        resp.raise_for_status()
        data = resp.json()
        if data.get('latitude') and data.get('longitude'):
            return {'lat': float(data['latitude']), 'lng': float(data['longitude'])}
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Speech-to-text (micrófono)
# ---------------------------------------------------------------------------

def dictar_direccion():
    """Intenta capturar una dirección por micrófono vía speech-to-text.

    Estrategia de fallback:
    1. Android: ``android.speech`` intent (si está disponible).
    2. Escritorio: biblioteca ``SpeechRecognition`` con Google Web Speech API.
    3. Si ninguna opción está disponible, devuelve cadena vacía y muestra
       un mensaje informativo.

    Returns:
        str: Texto dictado o ``''`` si no fue posible.
    """
    if _is_android():
        try:
            from jnius import autoclass, cast

            Intent = autoclass('android.content.Intent')
            RecognizerIntent = autoclass('android.speech.RecognizerIntent')
            intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                            RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, 'es-ES')
            from android import mActivity
            mActivity.startActivityForResult(intent, 1001)
            return ''
        except Exception as exc:
            print(f'No se pudo iniciar reconocimiento de voz en Android: {exc}')
            return ''

    try:
        import speech_recognition as sr

        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            print('Escuchando dirección…')
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
        text = recognizer.recognize_google(audio, language='es-ES')
        return text.strip()
    except ImportError:
        print('speech_recognition no está instalado; usa pip install SpeechRecognition.')
    except Exception as exc:
        print(f'Error en reconocimiento de voz: {exc}')
    return ''


# ---------------------------------------------------------------------------
# Búsqueda manual de dirección
# ---------------------------------------------------------------------------

def buscar_direccion_texto(texto):
    """Geocodifica *texto* libre (dirección sin código postal separado).

    Returns:
        dict or None: Parada con campos ``lat``, ``lng``, ``address``,
                      ``prioridad`` o ``None`` si no se pudo resolver.
    """
    texto = (texto or '').strip()
    if not texto:
        return None

    if requests is None:
        print('requests no está instalado.')
        return None
    if not API_KEY:
        print('No hay API key configurada; se omite la geocodificación.')
        return None

    url = 'https://maps.googleapis.com/maps/api/geocode/json'
    params = {'address': texto, 'key': API_KEY}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        res = resp.json()
    except Exception as exc:
        print(f'Error al geocodificar "{texto}": {exc}')
        return None

    if res.get('status') == 'OK' and res.get('results'):
        loc = res['results'][0]['geometry']['location']
        return {
            'lat': loc['lat'],
            'lng': loc['lng'],
            'address': res['results'][0].get('formatted_address', texto),
            'prioridad': 'media',
            'estado': 'pendiente',
        }
    print(f'No se encontraron resultados para "{texto}".')
    return None


# ---------------------------------------------------------------------------
# Eliminar parada
# ---------------------------------------------------------------------------

def eliminar_parada(paradas, indice):
    """Elimina la parada en *indice* de la lista *paradas* in-place.

    Returns:
        bool: ``True`` si se eliminó, ``False`` si el índice es inválido.
    """
    if not isinstance(paradas, list) or not (0 <= indice < len(paradas)):
        return False
    paradas.pop(indice)
    return True


def priorizar_paradas(paradas, modo='moto', hora_actual=None, origen_lat=None, origen_lng=None):
    """Ordena las paradas aplicando optimización de ruta y regla de las 19:00.

    Regla de las 19:00 (hora local)
    --------------------------------
    Si ``hora_actual`` (entero 0-23) es >= 19, las paradas **pendientes** se
    reordenan primero por prioridad (alta > media > baja) y dentro de cada
    grupo de prioridad se aplica la heurística del vecino más cercano para
    minimizar la distancia recorrida.

    Antes de las 19:00 se aplica solo la heurística del vecino más cercano
    teniendo en cuenta el modo de transporte (pie/coche/moto no cambia la
    heurística pero el parámetro queda disponible para futuras integraciones
    con la Directions API).

    Args:
        paradas: Lista de dicts con al menos ``lat``, ``lng`` y ``prioridad``.
        modo: ``'pie'``, ``'coche'`` o ``'moto'`` (por defecto ``'moto'``).
        hora_actual: Hora local (0-23).  Si es ``None`` se usa
            ``datetime.now().hour``.
        origen_lat: Latitud actual del repartidor (opcional).
        origen_lng: Longitud actual del repartidor (opcional).

    Returns:
        list: Nueva lista de paradas ordenadas.
    """
    if not paradas:
        return []

    modo = (modo or 'moto').lower().strip()
    if modo not in {'pie', 'moto', 'coche'}:
        modo = 'moto'

    if hora_actual is None:
        hora_actual = datetime.now().hour

    paradas_validas = [p for p in paradas if isinstance(p, dict)]

    if hora_actual >= 19:
        # Regla 19:00: prioridad primero, luego nearest-neighbor por grupo
        grupos = {prioridad: [] for prioridad in PRIORITY_ORDER}
        for p in paradas_validas:
            prioridad = str(p.get('prioridad', 'media')).lower()
            grupos[prioridad if prioridad in grupos else 'media'].append(p)

        resultado = []
        cur_lat, cur_lng = origen_lat, origen_lng
        for nivel in PRIORITY_ORDER:
            grupo_ordenado = _nearest_neighbor(grupos[nivel], cur_lat, cur_lng)
            if grupo_ordenado:
                resultado.extend(grupo_ordenado)
                ultimo = grupo_ordenado[-1]
                if coordenadas_validas(ultimo.get('lat'), ultimo.get('lng')):
                    cur_lat, cur_lng = ultimo['lat'], ultimo['lng']
        return resultado

    # Antes de las 19:00: optimización por vecino más cercano globalmente
    return _nearest_neighbor(paradas_validas, origen_lat, origen_lng)


def generar_url_ubicacion_individual(lat, lng, nombre=None, zoom=15):
    """Genera una URL web de Google Maps para una ubicación concreta."""
    if not coordenadas_validas(lat, lng):
        return 'No hay coordenadas válidas para abrir Google Maps.'
    query = f'{lat},{lng}'
    url = f'https://maps.google.com/?q={quote(query, safe=",")}'
    if nombre:
        url += f'&label={quote(normalizar_direccion(nombre))}'
    if zoom is not None:
        url += f'&z={int(zoom)}'
    return url


def resumir_ruta(paradas, modo='moto', hora_actual=None, origen_lat=None, origen_lng=None):
    """Calcula distancia, tiempo aproximado y orden de visita de la ruta."""
    if not paradas or not coordenadas_validas(origen_lat, origen_lng):
        return None
    paradas_ordenadas = priorizar_paradas(
        paradas,
        modo=modo,
        hora_actual=hora_actual,
        origen_lat=origen_lat,
        origen_lng=origen_lng,
    )
    paradas_ordenadas = [
        parada for parada in paradas_ordenadas
        if isinstance(parada, dict) and coordenadas_validas(parada.get('lat'), parada.get('lng'))
    ]
    if not paradas_ordenadas:
        return None

    total_distancia_km = 0.0
    segmentos = []
    actual_lat, actual_lng = origen_lat, origen_lng
    for numero, parada in enumerate(paradas_ordenadas, start=1):
        distancia = _haversine(actual_lat, actual_lng, parada['lat'], parada['lng'])
        total_distancia_km += distancia
        segmentos.append({
            'numero': numero,
            'nombre': parada.get('nombre') or parada.get('address') or f'Parada {numero}',
            'address': parada.get('address', ''),
            'lat': parada['lat'],
            'lng': parada['lng'],
            'distancia_km': round(distancia, 2),
        })
        actual_lat, actual_lng = parada['lat'], parada['lng']

    retorno_km = _haversine(actual_lat, actual_lng, origen_lat, origen_lng)
    total_distancia_km += retorno_km
    velocidad = TRANSPORT_SPEEDS_KMH.get((modo or 'moto').lower().strip(), TRANSPORT_SPEEDS_KMH['moto'])
    tiempo_total_min = round((total_distancia_km / velocidad) * 60) if velocidad else 0
    return {
        'paradas': segmentos,
        'distancia_total_km': round(total_distancia_km, 2),
        'tiempo_total_min': int(tiempo_total_min),
        'retorno_km': round(retorno_km, 2),
    }


def generar_ruta_maps(paradas, modo='moto', hora_actual=None, origen_lat=None, origen_lng=None):
    """Genera la URL de Google Maps con las paradas optimizadas.

    Args:
        paradas: Lista de dicts de paradas.
        modo: Modo de transporte (``'pie'``, ``'coche'``, ``'moto'``).
        hora_actual: Hora local (0-23) para la regla de las 19:00.
        origen_lat: Latitud actual del repartidor (opcional).
        origen_lng: Longitud actual del repartidor (opcional).

    Returns:
        str: URL de Google Maps o mensaje de error.
    """
    if not paradas:
        return 'No hay paradas'

    if not coordenadas_validas(origen_lat, origen_lng):
        return (
            'No hay una ubicación de origen válida. Activa la ubicación del '
            'dispositivo, pulsa "Ubicación" y vuelve a intentarlo.'
        )

    paradas_invalidas = [
        p for p in paradas
        if not isinstance(p, dict)
        or not coordenadas_validas(p.get('lat'), p.get('lng'))
    ]
    if paradas_invalidas:
        return (
            'Hay paradas sin coordenadas válidas. Corrige o elimina esas '
            'direcciones antes de optimizar la ruta.'
        )

    paradas_priorizadas = [
        p for p in priorizar_paradas(paradas, modo, hora_actual, origen_lat, origen_lng)
        if coordenadas_validas(p.get('lat'), p.get('lng'))
    ]
    if not paradas_priorizadas:
        return 'No hay paradas con coordenadas válidas para abrir Google Maps.'

    travelmode_map = {'pie': 'walking', 'coche': 'driving', 'moto': 'driving'}
    travelmode = travelmode_map.get((modo or 'moto').lower().strip(), 'driving')

    base_url = f'https://www.google.com/maps/dir/?api=1&travelmode={travelmode}'
    origen = f'&origin={quote(f"{origen_lat},{origen_lng}", safe=",")}'
    # A delivery route is closed: the current depot is both origin and destination.
    destino = f'&destination={quote(f"{origen_lat},{origen_lng}", safe=",")}'
    w_coords = [quote(f"{p['lat']},{p['lng']}", safe=',') for p in paradas_priorizadas]
    waypoints = '&waypoints=' + '|'.join(w_coords)

    return base_url + origen + destino + waypoints


def main():
    filename = DEFAULT_PHOTO_FILENAME
    try:
        if os.path.exists(filename):
            print(f'Usando imagen existente: {filename}')
        else:
            filename = take_photo(filename)
            print(f'Foto preparada como {filename}')
    except Exception as err:
        print(f'Error al preparar la imagen: {err}')

    direccion, cp = procesar_imagen(filename)
    print(f'\nResultado -> Dirección: {direccion} | CP: {cp}')

    if direccion and cp:
        geo = obtener_coordenadas(direccion, cp)
        if geo:
            geo = asignar_prioridad(geo, 'media')
            lista_paradas.append(geo)
            print(f'Añadido a la ruta con prioridad {geo["prioridad"]}: {geo["address"]}')
        else:
            print('No se pudo obtener coordenadas para la dirección proporcionada.')
    else:
        print('No hay dirección o código postal válidos para geocodificar.')

    link = generar_ruta_maps(lista_paradas, 'moto')
    print(f'\nLINK DE REPARTO: \n{link}')


if __name__ == '__main__':
    main()
