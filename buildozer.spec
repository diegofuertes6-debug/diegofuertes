[app]
title = Repartidor
package.name = repartidorapp
package.domain = org.test
source.dir = .
source.include_exts = py,png,jpg,json
version = 1.0.0
requirements = python3,kivy,requests,plyer,openssl,urllib3
orientation = portrait
android.permissions = INTERNET, CAMERA, ACCESS_FINE_LOCATION, WRITE_EXTERNAL_STORAGE, READ_EXTERNAL_STORAGE, RECORD_AUDIO
android.api = 31
android.minapi = 21
android.ndk = 25b
android.ndk_path = %(ANDROID_SDK_ROOT)s/ndk/25.2.9519653
android.sdk_path = %(ANDROID_SDK_ROOT)s
android.build_tools_version = 35.0.0
android.archs = arm64-v8a