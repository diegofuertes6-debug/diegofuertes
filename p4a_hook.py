"""python-for-android build hook.

El OCR por cámara fue retirado, por lo que ya no se modifica el manifest.
"""


def patch_manifest(_manifest_path):
    return None


def after_apk_build(_toolchain):
    return None
