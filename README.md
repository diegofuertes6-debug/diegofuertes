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
- **Prioridades**: asigna alta (roja), media (naranja) o baja (verde).
- **Paquetería y cartas**: elige paquetería Urgente/Normal y el tipo de carta;
  los valores antiguos se normalizan al cargarlos en una parada nueva.
- **Modo de transporte**: a pie / coche / moto.
- **Optimización de ruta cerrada**: usa la posición actual como depósito y
  genera una ruta que sale y regresa exactamente a esa misma coordenada.
- **Regla de las 19:00**: a partir de las 19:00 hora local las paradas pendientes se reordenan primero por prioridad (alta > media > baja) y dentro de cada grupo se aplica la optimización de vecino más cercano.

---

## Instalación y ejecución en escritorio

### Requisitos

- Python 3.10 o superior
- pip

### Pasos

```bash
# 1. Clona el repositorio
git clone https://github.com/diegofuertes6-debug/diegofuertes.git
cd diegofuertes

# 2. (Recomendado) Crea un entorno virtual
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
.venv\Scripts\activate      # Windows

# 3. Instala dependencias
pip install kivy requests python-dotenv

# Opcional: OCR (cámara en escritorio)
pip install pytesseract opencv-python

# Opcional: reconocimiento de voz en escritorio
pip install SpeechRecognition pyaudio

# 4. Configura la API key de Google Maps (ver sección siguiente)
cp .env.example .env
# Edita .env y añade tu clave: GOOGLE_MAPS_API_KEY=AIzaSy...

# 5. Ejecuta la app
python main.py
```

---

## Configuración de la API key de Google Maps

La app carga la API key automáticamente desde estas fuentes (en orden de prioridad):

### Opción 1 — Archivo `.env` (recomendado para desarrollo local)

Copia el archivo de ejemplo y rellena tu clave:

```bash
cp .env.example .env
# Edita .env y sustituye TU_API_KEY_AQUÍ por tu clave real
```

El archivo `.env` **nunca** se sube al repositorio (está en `.gitignore`).

### Opción 2 — Variable de entorno

```bash
# Linux / macOS
export GOOGLE_MAPS_API_KEY="AIzaSy..."
python main.py

# Windows PowerShell
$env:GOOGLE_MAPS_API_KEY="AIzaSy..."
python main.py
```

### Opción 3 — `webServerApiSettings.json` (legacy)

Crea `webServerApiSettings.json` en la raíz del proyecto:

```json
{
  "googleMapsApiKey": "AIzaSy..."
}
```

Este archivo también está en `.gitignore` y no debe subirse al repositorio.

### Obtener una API key

1. Ve a [Google Cloud Console](https://console.cloud.google.com/).
2. Crea un proyecto (o selecciona uno existente).
3. Activa las APIs: **Geocoding API** y **Maps JavaScript API**.
4. Ve a **Credenciales → Crear credencial → Clave de API**.
5. Copia la clave (comienza con `AIza...`).

> **Nota**: sin API key la app no puede geocodificar direcciones.
> La parada muestra un error de geolocalización y permite corregir o
> reintentar; nunca se inventan coordenadas.

---

## Solución de problemas (Troubleshooting)

### Google Maps no se inicia / no hay coordenadas

**Síntoma**: la app muestra `API key no configurada` en los logs o las
paradas no obtienen coordenadas.

**Causa**: ninguna de las tres fuentes de configuración tiene una key válida.

**Solución**:

1. Verifica que la key esté configurada:

   ```bash
   python -c "import repartidor; print('API_KEY:', repartidor.API_KEY[:10] + '...' if repartidor.API_KEY else 'NO CONFIGURADA')"
   ```

2. Si muestra `NO CONFIGURADA`, sigue los pasos de la sección anterior.

3. Asegúrate de que la key tiene habilitadas las APIs **Geocoding API** y
   **Maps JavaScript API** en Google Cloud Console.

### Kivy no arranca en escritorio

Instala los binarios de Kivy para tu sistema operativo siguiendo la
[guía oficial](https://kivy.org/doc/stable/gettingstarted/installation.html).
En Linux puede ser necesario:

```bash
sudo apt-get install libgl1-mesa-dev libgles2-mesa-dev
```

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
- Pulsa el único botón de escáner **📷**.
- En Android abre la cámara nativa y procesa la foto localmente con ML Kit.
- Revisa la dirección propuesta. Si hay varios candidatos, selecciónala en la
  lista; también puedes editar el texto antes de pulsar **Añadir parada**.
- El archivo temporal se elimina al completar o fallar el OCR.
- En escritorio intenta capturar un fotograma con OpenCV (`cv2`).
- El texto de la imagen se extrae con `pytesseract` (requiere Tesseract OCR instalado).

### Micrófono
- Pulsa el único botón de voz **🎙**.
- En Android lanza el intent `ACTION_RECOGNIZE_SPEECH` del sistema.
- Revisa o corrige el texto reconocido y pulsa **Añadir parada**.
- En escritorio usa la biblioteca `SpeechRecognition` con la Google Web Speech API.
  - Instálala con: `pip install SpeechRecognition pyaudio`
- Si el reconocimiento falla, la app muestra un mensaje y puedes usar la búsqueda manual.

### Ubicación
- La app solicita la ubicación al iniciar, con una explicación contextual.
- El control de ruta solicita la posición si aún no está disponible. Si los
  servicios están apagados, ofrece abrir el panel de ubicación de
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

## Estructura del proyecto

```
diegofuertes/
├── main.py                   # Aplicación Kivy (UI principal)
├── repartidor.py             # Lógica de negocio: geocodificación, rutas, prioridades
├── android_services.py       # Servicios Android (cámara, micrófono, ubicación)
├── p4a_hook.py               # Hook de python-for-android
├── buildozer.spec            # Configuración de compilación APK
├── .env.example              # Plantilla de configuración (copiar a .env)
├── android_resources/        # Recursos XML de Android (FileProvider, etc.)
├── tests/
│   └── test_smoke.py         # Suite de pruebas unitarias
└── .github/
    └── workflows/
        └── android-apk.yml   # CI: compila APK debug en GitHub Actions
```

---

## Compilar APK

1. Instala Buildozer y las dependencias de Android.
2. Desde la carpeta del proyecto ejecuta:

   ```bash
   buildozer android debug
   ```

El build fija `python-for-android` en `v2024.01.21`, compatible con
Buildozer 1.5.0 y la toolchain Android usada por el workflow.

---

## CI/CD con GitHub Actions

El workflow `.github/workflows/android-apk.yml` compila la APK debug
automáticamente en cada push a la rama `feature/enrrutador-prioridades`
o cuando se lanza manualmente.

### Secrets necesarios para APK firmada (release)

Para publicar una APK firmada, crea los siguientes secrets en
**GitHub → Settings → Secrets and variables → Actions**:

| Secret | Descripción |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | Keystore codificado en base64 |
| `ANDROID_KEY_ALIAS` | Alias de la clave dentro del keystore |
| `ANDROID_KEYSTORE_PASSWORD` | Contraseña del keystore |
| `ANDROID_KEY_PASSWORD` | Contraseña de la clave |
| `GOOGLE_MAPS_API_KEY` | API key de Google Maps para el build |

### Generar el keystore y codificarlo

```bash
# 1. Generar keystore
keytool -genkeypair -v -keystore release.jks -alias repartidor \
        -keyalg RSA -keysize 2048 -validity 10000

# 2. Codificar en base64 (Linux/macOS)
base64 -w 0 release.jks

# Pega el resultado como valor del secret ANDROID_KEYSTORE_BASE64
```

> ⚠️ **Nunca subas el archivo `.jks` al repositorio.** Está incluido en
> `.gitignore` para evitar exposición accidental.

---

## Ejecutar pruebas

```bash
python -m pytest tests/ -v
```

O con el runner estándar de unittest:

```bash
python -m unittest discover tests -v
```

