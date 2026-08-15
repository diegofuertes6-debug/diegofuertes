"""python-for-android build hook for manifest elements unsupported by Buildozer."""

from pathlib import Path


PROVIDER_MARKER = 'org.test.repartidorapp.fileprovider'
PROVIDER_XML = f'''
        <provider
            android:name="androidx.core.content.FileProvider"
            android:authorities="{PROVIDER_MARKER}"
            android:exported="false"
            android:grantUriPermissions="true">
            <meta-data
                android:name="android.support.FILE_PROVIDER_PATHS"
                android:resource="@xml/provider_paths" />
        </provider>
'''
CAMERA_ACTION = 'android.media.action.IMAGE_CAPTURE'
CAMERA_QUERY_XML = f'''
    <queries>
        <intent>
            <action android:name="{CAMERA_ACTION}" />
        </intent>
    </queries>
'''


def inject_file_provider(manifest_path):
    """Insert the FileProvider as an application child, exactly once."""
    manifest_path = Path(manifest_path)
    manifest = manifest_path.read_text(encoding='utf-8')
    if PROVIDER_MARKER in manifest:
        return
    closing_tag = '</application>'
    if closing_tag not in manifest:
        raise RuntimeError(f'No se encontró {closing_tag} en {manifest_path}')
    manifest = manifest.replace(closing_tag, PROVIDER_XML + closing_tag, 1)
    manifest_path.write_text(manifest, encoding='utf-8')


def inject_camera_query(manifest_path):
    """Declare camera Intent visibility as a direct manifest child."""
    manifest_path = Path(manifest_path)
    manifest = manifest_path.read_text(encoding='utf-8')
    if CAMERA_ACTION in manifest:
        return
    application_tag = '<application'
    if application_tag not in manifest:
        raise RuntimeError(f'No se encontró {application_tag} en {manifest_path}')
    manifest = manifest.replace(
        application_tag,
        CAMERA_QUERY_XML + application_tag,
        1,
    )
    manifest_path.write_text(manifest, encoding='utf-8')


def patch_manifest(manifest_path):
    inject_camera_query(manifest_path)
    inject_file_provider(manifest_path)


def after_apk_build(_toolchain):
    """Patch both Gradle's manifest and p4a's compatibility copy."""
    patch_manifest('src/main/AndroidManifest.xml')
    patch_manifest('AndroidManifest.xml')
