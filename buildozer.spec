[app]

# Información básica
title = Repartidor
package.name = repartidor
package.domain = org.diegofuertes
source.dir = .
source.include_exts = py,png,jpg,kv,atlas
version = 1.0

# Dependencias Python
requirements = python3,kivy,pyjnius,android

# Permisos de Android
# RECEIVE_SMS y READ_SMS necesarios para leer el código OTP automáticamente
android.permissions = RECEIVE_SMS, READ_SMS, INTERNET, ACCESS_NETWORK_STATE

# Servicios de Google Play para SMS Retriever API
android.gradle_dependencies = com.google.android.gms:play-services-auth:20.7.0, com.google.android.gms:play-services-auth-api-phone:18.0.2

# SDK Android
android.api = 33
android.minapi = 21
android.sdk = 33
android.ndk = 25b
android.ndk_api = 21
android.archs = arm64-v8a, armeabi-v7a

# Orientación
orientation = portrait

# Icono y pantalla de carga (opcional)
# icon.filename = %(source.dir)s/data/icon.png
# presplash.filename = %(source.dir)s/data/presplash.png

[buildozer]
log_level = 2
warn_on_root = 1
