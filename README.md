# Repartidor

Aplicación Kivy para Android con login simple, toma de foto y generación de ruta.

## Compilar APK

1. Instala Buildozer y las dependencias de Android.
2. Desde la carpeta del proyecto ejecuta:
   - `buildozer android debug`

## Notas

- La cámara se intenta abrir de forma nativa en Android mediante la intención del sistema.
- Si el entorno no tiene la cámara o permisos, la app mostrará un mensaje en pantalla.
