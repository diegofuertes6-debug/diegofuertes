[app]
title = Repartidor
package.name = repartidor
package.domain = org.test
source.dir = .
source.include_exts = py,png,jpg,jpeg,json,txt
version = 1.0.1
requirements = python3,kivy==2.3.1,requests,pillow,python-dotenv
orientation = portrait
fullscreen = 0
android.permissions = INTERNET,CAMERA,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
android.api = 33
android.minapi = 24
android.ndk = 25b
android.archs = arm64-v8a
android.allow_backup = False
android.accept_sdk_license = True
android.gradle_dependencies = androidx.core:core-ktx:1.13.0
p4a.branch = master

[buildozer]
log_level = 2
warn_on_root = 0
