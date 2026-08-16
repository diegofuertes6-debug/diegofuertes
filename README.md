# Repartidor

Aplicación Kivy para Android con login, geolocalización, gestión de paradas con prioridad y optimización de rutas.

## Características

- **Geolocalización**: muestra la posición actual del repartidor (requiere permiso de ubicación).
- **Entrada de paradas** por tres canales:
  - 📷 Cámara: toma una foto, propone una o varias direcciones extraídas por
    OCR y permite seleccionar, editar y confirmar antes de añadir.
  - 🎙 Micrófono: dicta la dirección por voz (speech-to-text), revisa el texto
    reconocido y confírmalo antes de añadir.
  - 🔍 Búsqueda manual: escribe la dirección y pulsa la lupa o Enter.
  Los tres canales comparten validación, geocodificación y detección de
  duplicados, y siempre muestran si la parada se añadió o por qué se rechazó.
- **Prioridades**: asigna prioridad alta / media / baja a cada parada.
- **Paquetería y notificación**: selectores contextuales que guardan ambas
  opciones en cada parada nueva.
- **Modo de transporte**: a pie / coche / moto.
- **Optimización de ruta cerrada**: usa la posición actual como depósito y
  genera una ruta que sale y regresa exactamente a esa misma coordenada.
- **Regla de las 19:00**: a partir de las 19:00 hora local las paradas pendientes se reordenan primero por prioridad (alta > media > baja) y dentro de cada grupo se aplica la optimización de vecino más cercano.

---

## Configuración de la API key de Google Maps

1. Crea (o edita) el archivo `webServerApiSettings.json` en la raíz del proyecto:

   ```json
   {
     "googleMapsApiKey": "TU_API_KEY_AQUÍ"
   }
   ```

2. Alternativamente, define la variable de entorno `GOOGLE_MAPS_API_KEY` o añade la clave en un archivo `.env`:

   ```
   GOOGLE_MAPS_API_KEY=TU_API_KEY_AQUÍ
   ```

3. La API key debe tener habilitadas las APIs **Geocoding** y **Maps JavaScript**.

> **Nota**: sin API key la app no puede hacer elegible una dirección para la
> ruta. La parada muestra error de geolocalización y permite corregir o
> reintentar; nunca se inventan coordenadas.

---

## Permisos necesarios

### Android (`buildozer.spec`)

| Permiso | Para qué se usa |
|---|---|
| `INTERNET` | Llamadas a la API de geocodificación de Google Maps |
| `ACCESS_COARSE_LOCATION` | Permitir que Android ofrezca ubicación aproximada |
| `ACCESS_FINE_LOCATION` | Obtener ubicación precisa si el usuario la autoriza |
| `CAMERA` | Captura de foto para OCR de dirección |
| `RECORD_AUDIO` | Reconocimiento de voz (micrófono) |

Al arrancar se explica y solicita el permiso de ubicación porque la posición
actual es el depósito obligatorio de la ruta. Cámara y micrófono se solicitan
en contexto al usar cada función. Si el usuario deniega ubicación, la app
respeta la decisión y no repite automáticamente el prompt. Las imágenes se
capturan en almacenamiento privado mediante `FileProvider`, se eliminan después
del OCR y no quedan en la galería; la app tampoco guarda el audio reconocido.

---

## Uso de cámara y micrófono

### Cámara
- Pulsa el botón **📷 Cámara**.
- En Android abre la cámara nativa y procesa la foto localmente con ML Kit.
- Revisa la dirección propuesta. Si hay varios candidatos, selecciónala en la
  lista; también puedes editar el texto antes de pulsar **Añadir parada**.
- El archivo temporal se elimina al completar o fallar el OCR.
- En escritorio intenta capturar un fotograma con OpenCV (`cv2`).
- El texto de la imagen se extrae con `pytesseract` (requiere Tesseract OCR instalado).

### Micrófono
- Pulsa el botón **🎙 Micrófono**.
- En Android lanza el intent `ACTION_RECOGNIZE_SPEECH` del sistema.
- Revisa o corrige el texto reconocido y pulsa **Añadir parada**.
- En escritorio usa la biblioteca `SpeechRecognition` con la Google Web Speech API.
  - Instálala con: `pip install SpeechRecognition pyaudio`
- Si el reconocimiento falla, la app muestra un mensaje y puedes usar la búsqueda manual.

### Ubicación
- La app solicita la ubicación al iniciar, con una explicación contextual.
- Si los servicios están apagados, ofrece abrir el panel de ubicación de
  Android. Al regresar, comprueba el proveedor y reintenta la posición sin
  repetir diálogos en bucle.
- Android permite conceder ubicación aproximada o precisa; la app usa la
  posición disponible como origen y destino idénticos al ordenar y abrir la ruta.
- La optimización se bloquea con un mensaje explicativo si la ubicación está
  desactivada, falta el permiso, el origen no es válido o alguna parada no pudo
  geocodificarse.

---

## Flujo de priorización de las 19:00

La hora local se obtiene con `datetime.now().hour`.

| Momento | Comportamiento |
|---|---|
| Antes de las 19:00 | Las paradas se ordenan por la heurística del vecino más cercano (minimiza distancia total). |
| A partir de las 19:00 | Se aplica la **regla de las 19:00**: primero todas las paradas de prioridad **alta**, luego **media**, luego **baja**. Dentro de cada grupo sigue aplicándose la heurística del vecino más cercano. |

El recálculo se dispara automáticamente:
- Cada minuto (reloj interno de la app).
- Al añadir o eliminar una parada.
- Al cambiar el modo de transporte.
- Al abrir la app si ya son las 19:00 o más.

---

## Compilar APK

1. Instala Buildozer y las dependencias de Android.
2. Desde la carpeta del proyecto ejecuta:

   ```bash
   buildozer android debug
   ```

El build fija `python-for-android` en `v2024.01.21`, compatible con
Buildozer 1.5.0 y la toolchain Android usada por el workflow.

## Generar APK firmada y publicarla en GitHub

1. Genera un keystore localmente:

   ```bash
   keytool -genkeypair -v -keystore release.jks -alias repartidor -keyalg RSA -keysize 2048 -validity 10000
   ```

2. Crea estos secrets en GitHub:
   - `ANDROID_KEYSTORE_BASE64`
   - `ANDROID_KEY_ALIAS`
   - `ANDROID_KEYSTORE_PASSWORD`
   - `ANDROID_KEY_PASSWORD`

3. Codifica el keystore en base64:

   ```bash
   base64 -w 0 release.jks   # Linux/macOS
   ```

4. Haz push a `main`/`master` o lanza el workflow manualmente.

---

## Ejecutar pruebas

```bash
python -m unittest discover tests -v
```
