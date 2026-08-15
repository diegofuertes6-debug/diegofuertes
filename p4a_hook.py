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


def after_apk_build(_toolchain):
    """Patch both Gradle's manifest and p4a's compatibility copy."""
    inject_file_provider('src/main/AndroidManifest.xml')
    inject_file_provider('AndroidManifest.xml')
