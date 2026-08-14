# -*- coding: utf-8 -*-
"""Aplicación de reparto robusta para escritorio y Android."""
import json
import os
import re
from datetime import datetime

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

    texto = re.sub(r'\s+', ' ', texto).strip()
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
        return {'lat': loc['lat'], 'lng': loc['lng'], 'address': full_address, 'prioridad': 'media'}
    return None


def asignar_prioridad(parada, prioridad):
    if not isinstance(parada, dict):
        return parada
    prioridad_valida = prioridad.lower().strip() if isinstance(prioridad, str) else 'media'
    if prioridad_valida not in {'baja', 'media', 'alta'}:
        prioridad_valida = 'media'
    parada['prioridad'] = prioridad_valida
    return parada


def priorizar_paradas(paradas, modo='moto'):
    if not paradas:
        return []

    modo = (modo or 'moto').lower().strip()
    if modo not in {'pie', 'moto', 'coche'}:
        modo = 'moto'

    orden = {'alta': 0, 'media': 1, 'baja': 2}
    paradas_ordenadas = sorted(
        (p for p in paradas if isinstance(p, dict)),
        key=lambda p: orden.get(p.get('prioridad', 'media'), 1)
    )

    if datetime.now().hour >= 19:
        paradas_altas = [p for p in paradas_ordenadas if p.get('prioridad') == 'alta']
        paradas_restantes = [p for p in paradas_ordenadas if p.get('prioridad') != 'alta']
        return paradas_altas + paradas_restantes

    return paradas_ordenadas


def generar_ruta_maps(paradas, modo='moto'):
    if not paradas:
        return 'No hay paradas'

    paradas_priorizadas = [
        p for p in priorizar_paradas(paradas, modo)
        if isinstance(p.get('lat'), (int, float)) and isinstance(p.get('lng'), (int, float))
    ]
    if not paradas_priorizadas:
        return 'No hay paradas con coordenadas válidas'

    base_url = 'https://www.google.com/maps/dir/?api=1'
    destino = f'&destination={paradas_priorizadas[-1]["lat"]},{paradas_priorizadas[-1]["lng"]}'
    waypoints = ''
    if len(paradas_priorizadas) > 1:
        w_coords = [f"{p['lat']},{p['lng']}" for p in paradas_priorizadas[:-1]]
        waypoints = '&waypoints=' + '|'.join(w_coords)

    return base_url + destino + waypoints


def main():
    try:
        from auth import run_auth_flow
        run_auth_flow()
    except (ImportError, KeyboardInterrupt):
        pass

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
