[app]
title = Repartidor
package.name = repartidor
package.domain = org.test
source.dir = .
source.include_exts = py,png,jpg,jpeg,json,txt
version = 1.0.1
requirements = python3,kivy,requests,Pillow
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,CAMERA,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.api = 35
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.allow_backup = True
android.gradle_dependencies = androidx.core:core-ktx:1.6.0

[buildozer]
log_level = 2
warn_on_root = 0

[python]
version = 3.11
