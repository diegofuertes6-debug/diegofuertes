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


def _take_photo_android(target_path):
    try:
        from android.permissions import Permission, request_permissions

        request_permissions([
            Permission.CAMERA,
            Permission.READ_EXTERNAL_STORAGE,
            Permission.WRITE_EXTERNAL_STORAGE,
        ])
    except (ImportError, AttributeError) as exc:
        print(f'No se pudieron solicitar permisos de cámara: {exc}')

    try:
        from android import activity
        from jnius import autoclass

        Intent = autoclass('android.content.Intent')
        MediaStore = autoclass('android.provider.MediaStore')
        Uri = autoclass('android.net.Uri')
        File = autoclass('java.io.File')

        java_file = File(target_path)
        uri = Uri.fromFile(java_file)
        intent = Intent(MediaStore.ACTION_IMAGE_CAPTURE)
        intent.putExtra(MediaStore.EXTRA_OUTPUT, uri)
        activity.startActivity(intent)
        return target_path
    except (ImportError, AttributeError) as exc:
        print(f'No se pudo abrir la cámara nativa: {exc}')
        return target_path


def take_photo(filename='foto_direccion.jpg', quality=0.8):
    del quality
    target_path = _resolve_path(filename)
    if os.path.exists(target_path):
        return target_path

    if _is_android():
        return _take_photo_android(target_path)

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
    target_path = _resolve_path(path)
    if not os.path.isfile(target_path):
        print(f'No existe la imagen: {target_path}')
        return '', ''

    if pytesseract is None or Image is None:
        print('pytesseract/Pillow no están disponibles para procesar la imagen.')
        return '', ''

    try:
        with Image.open(target_path) as image:
            texto = pytesseract.image_to_string(image, lang='eng+spa')
    except (OSError, ValueError) as exc:
        print(f'No se pudo procesar la imagen: {exc}')
        return '', ''

    return extraer_direccion_texto_ocr(texto)


def extraer_direccion_texto_ocr(texto):
    """Extract a likely Spanish street address and postal code from OCR text."""
    texto = re.sub(r'\s+', ' ', texto or '').strip()
    if not texto:
        return '', ''
    print('\n--- Texto detectado ---')
    print(texto)

    cp_match = re.search(r'\b\d{5}\b', texto)
    cp_final = cp_match.group() if cp_match else ''

    patrones = [
        r'\b(?:Calle|Calleja|C/|C\.\/|Avda|Avenida|Avinguda|Plaza|Paseo|Carrera|Camino|Ronda|Via)\b[^\n]{0,80}',
        r'\b(?:Calle|C/|Avda|Avenida|Plaza|Paseo)\b[^\n]{0,80}',
    ]
    direccion_final = ''
    for patron in patrones:
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            direccion_final = re.sub(r'\s+', ' ', match.group()).strip()
            break

    return direccion_final, cp_final


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
    if prioridad_valida not in {'baja', 'media', 'alta'}:
        prioridad_valida = 'media'
    parada['prioridad'] = prioridad_valida
    return parada


def _haversine(lat1, lng1, lat2, lng2):
    """Distancia en km entre dos puntos (fórmula haversine)."""
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _nearest_neighbor(paradas, origen_lat=None, origen_lng=None):
    """Ordena *paradas* con la heurística del vecino más cercano.

    Si no se dispone de coordenadas válidas en una parada se mantiene su
    posición relativa.  El punto de inicio puede ser la posición actual del
    repartidor (``origen_lat``/``origen_lng``) o, si es ``None``, el primer
    elemento de la lista.
    """
    candidatos = [p for p in paradas if isinstance(p.get('lat'), (int, float))
                  and isinstance(p.get('lng'), (int, float))]
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
            from android import activity
            activity.startActivityForResult(intent, 1001)
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
        orden = {'alta': 0, 'media': 1, 'baja': 2}
        grupos = {'alta': [], 'media': [], 'baja': []}
        for p in paradas_validas:
            grupos[p.get('prioridad', 'media')].append(p)

        resultado = []
        cur_lat, cur_lng = origen_lat, origen_lng
        for nivel in ('alta', 'media', 'baja'):
            grupo_ordenado = _nearest_neighbor(grupos[nivel], cur_lat, cur_lng)
            if grupo_ordenado:
                resultado.extend(grupo_ordenado)
                ultimo = grupo_ordenado[-1]
                if isinstance(ultimo.get('lat'), (int, float)):
                    cur_lat, cur_lng = ultimo['lat'], ultimo['lng']
        return resultado

    # Antes de las 19:00: optimización por vecino más cercano globalmente
    return _nearest_neighbor(paradas_validas, origen_lat, origen_lng)


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

    paradas_priorizadas = [
        p for p in priorizar_paradas(paradas, modo, hora_actual, origen_lat, origen_lng)
        if isinstance(p.get('lat'), (int, float)) and isinstance(p.get('lng'), (int, float))
    ]
    if not paradas_priorizadas:
        return 'No hay paradas con coordenadas válidas'

    travelmode_map = {'pie': 'walking', 'coche': 'driving', 'moto': 'driving'}
    travelmode = travelmode_map.get((modo or 'moto').lower().strip(), 'driving')

    base_url = f'https://www.google.com/maps/dir/?api=1&travelmode={travelmode}'
    destino = f'&destination={paradas_priorizadas[-1]["lat"]},{paradas_priorizadas[-1]["lng"]}'
    waypoints = ''
    if len(paradas_priorizadas) > 1:
        w_coords = [f"{p['lat']},{p['lng']}" for p in paradas_priorizadas[:-1]]
        waypoints = '&waypoints=' + '|'.join(w_coords)

    return base_url + destino + waypoints


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
