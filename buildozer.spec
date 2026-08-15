[app]
title = Repartidor
package.name = repartidorapp
package.domain = org.test
source.dir = .
source.include_exts = py,png,jpg,json
version = 1.0.0
requirements = python3,kivy,pyjnius,requests,plyer,openssl,urllib3
orientation = portrait
android.permissions = INTERNET,ACCESS_COARSE_LOCATION,ACCESS_FINE_LOCATION,CAMERA,RECORD_AUDIO
android.api = 33
android.minapi = 21
android.ndk = 25b
android.sdk_path =
android.archs = arm64-v8a
android.gradle_dependencies = com.google.mlkit:text-recognition:16.0.1
android.enable_androidx = True
p4a.branch = v2024.01.21