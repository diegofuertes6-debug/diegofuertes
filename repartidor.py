# -*- coding: utf-8 -*-
"""Aplicación de reparto con soporte para ejecutar fuera de Colab."""
import json
import os
import re
from base64 import b64decode
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
except Exception:
    load_dotenv = None

try:
    from IPython.display import display, Javascript
except Exception:
    display = None
    Javascript = None

try:
    from google.colab.output import eval_js
except Exception:
    eval_js = None

try:
    import pytesseract
except Exception:
    pytesseract = None

try:
    from PIL import Image
except Exception:
    Image = None

try:
    import requests
except Exception:
    requests = None


def take_photo(filename='foto_direccion.jpg', quality=0.8):
    if Javascript is None or display is None or eval_js is None:
        print('La captura de cámara requiere IPython/Colab; se omite en esta ejecución.')
        return filename

    js = Javascript('''
    async function takePhoto(quality) {
      const div = document.createElement('div');
      const capture = document.createElement('button');
      capture.textContent = 'CAPTURAR DIRECCIÓN';
      div.appendChild(capture);

      const video = document.createElement('video');
      video.style.display = 'block';
      const stream = await navigator.mediaDevices.getUserMedia({video: {facingMode: "environment"}});

      document.body.appendChild(div);
      div.appendChild(video);
      video.srcObject = stream;
      await video.play();

      google.colab.output.setIframeHeight(document.documentElement.scrollHeight, true);

      await new Promise((resolve) => capture.onclick = resolve);

      const canvas = document.createElement('canvas');
      canvas.width = video.videoWidth;
      canvas.height = video.videoHeight;
      canvas.getContext('2d').drawImage(video, 0, 0);
      stream.getVideoTracks()[0].stop();
      div.remove();
      return canvas.toDataURL('image/jpeg', quality);
    }
    ''')
    display(js)
    data = eval_js('takePhoto({})'.format(quality))
    binary = b64decode(data.split(',')[1])
    with open(filename, 'wb') as f:
        f.write(binary)
    return filename


def procesar_imagen(path):
    if pytesseract is None or Image is None:
        print('pytesseract/Pillow no están disponibles para procesar la imagen.')
        return '', ''

    texto = pytesseract.image_to_string(Image.open(path), lang='eng+spa')
    print('\n--- Texto detectado ---')
    print(texto)

    cp = re.search(r'\b\d{5}\b', texto)
    cp_final = cp.group() if cp else ''

    patrones = [
        r'(Calle\s+[A-Za-z0-9\s]+)',
        r'(Avda\.?\s+[A-Za-z0-9\s]+)',
        r'(C/\s*[A-Za-z0-9\s]+)'
    ]
    direccion_final = ''
    for p in patrones:
        m = re.search(p, texto, re.IGNORECASE)
        if m:
            direccion_final = m.group()
            break

    return direccion_final, cp_final


def cargar_api_key():
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env')

    if load_dotenv is not None and os.path.exists(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path, override=False)
    elif os.path.exists(dotenv_path):
        with open(dotenv_path, encoding='utf-8') as f:
            for line in f:
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

    settings_path = os.path.join(os.path.dirname(
        __file__), 'webServerApiSettings.json')
    if os.path.exists(settings_path):
        try:
            with open(settings_path, encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                for key in API_KEY_CANDIDATES:
                    value = data.get(key)
                    if isinstance(value, str) and value.strip() and value.strip() != 'TU_API_KEY_AQUÍ':
                        return value.strip()
        except Exception as e:
            print(f'No se pudo leer {settings_path}: {e}')

    return ''


API_KEY = cargar_api_key()

lista_paradas = []


def obtener_coordenadas(direccion, cp):
    if requests is None:
        print('requests no está instalado; se omite la geolocalización.')
        return None

    full_address = f'{direccion}, {cp}, España'
    url = 'https://maps.googleapis.com/maps/api/geocode/json'
    params = {'address': full_address, 'key': API_KEY}
    try:
        resp = requests.get(url, params=params, timeout=10)
        res = resp.json()
    except Exception as e:
        print(f'Error al solicitar geocodificación: {e}')
        return None

    if res.get('status') == 'OK' and res.get('results'):
        loc = res['results'][0]['geometry']['location']
        return {'lat': loc['lat'], 'lng': loc['lng'], 'address': full_address, 'prioridad': 'media'}
    return None


def asignar_prioridad(parada, prioridad):
    if not isinstance(parada, dict):
        return parada
    prioridad_valida = prioridad.lower().strip(
    ) if isinstance(prioridad, str) else 'media'
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

    ahora = datetime.now()
    es_tarde = ahora.hour >= 19

    orden = {'alta': 0, 'media': 1, 'baja': 2}
    paradas_ordenadas = sorted(
        paradas, key=lambda p: orden.get(p.get('prioridad', 'media'), 1))

    if es_tarde:
        paradas_altas = [
            p for p in paradas_ordenadas if p.get('prioridad') == 'alta']
        paradas_restantes = [
            p for p in paradas_ordenadas if p.get('prioridad') != 'alta']
        return paradas_altas + paradas_restantes

    if modo == 'pie':
        return paradas_ordenadas
    if modo == 'moto':
        return paradas_ordenadas
    if modo == 'coche':
        return paradas_ordenadas

    return paradas_ordenadas


def generar_ruta_maps(paradas, modo='moto'):
    if not paradas:
        return 'No hay paradas'

    paradas_priorizadas = priorizar_paradas(paradas, modo)
    base_url = 'https://www.google.com/maps/dir/?api=1'
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
            print(f'Foto guardada como {filename}')
    except Exception as err:
        print(f'Error al preparar la imagen: {err}')

    direccion, cp = procesar_imagen(filename)
    print(f'\nResultado -> Dirección: {direccion} | CP: {cp}')

    if direccion and cp:
        if not API_KEY:
            print('No hay API key configurada; se omite la geocodificación.')
        else:
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
