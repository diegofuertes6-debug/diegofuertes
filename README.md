# Repartidor

Aplicación Kivy para Android con login simple, toma de foto y generación de ruta.

## Compilar APK

1. Instala Buildozer y las dependencias de Android.
2. Desde la carpeta del proyecto ejecuta:
   - `buildozer android debug`

## Generar APK firmada y publicarla en GitHub

1. Genera un keystore localmente:
   - `keytool -genkeypair -v -keystore release.jks -alias repartidor -keyalg RSA -keysize 2048 -validity 10000`
2. Guarda la contraseña y el alias.
3. Crea estos secrets en GitHub:
   - `ANDROID_KEYSTORE_BASE64`
   - `ANDROID_KEY_ALIAS`
   - `ANDROID_KEYSTORE_PASSWORD`
   - `ANDROID_KEY_PASSWORD`
4. Codifica el keystore en base64 para el secret:
   - `base64 -w 0 release.jks` (Linux/macOS)
   - `certutil -encode release.jks release.txt` y usa el contenido del txt (Windows PowerShell)
5. Haz push a `main` o `master` o ejecuta el workflow manualmente desde la pestaña Actions.
6. La APK firmada quedará disponible como artefacto y como release en GitHub.

## Notas

- La cámara se intenta abrir de forma nativa en Android mediante la intención del sistema.
- Si el entorno no tiene la cámara o permisos, la app mostrará un mensaje en pantalla.
- Para descargar la APK final, ve a la pestaña Releases o Actions > artefactos del workflow.
