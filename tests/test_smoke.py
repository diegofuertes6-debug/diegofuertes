import unittest
import sys
import tempfile
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import main
import repartidor
import android_services
import p4a_hook


class PriorizacionTests(unittest.TestCase):
    """Pruebas de priorización de paradas y regla de las 19:00."""

    def _paradas(self):
        return [
            {'address': 'A', 'lat': 40.0, 'lng': -3.0, 'prioridad': 'baja', 'estado': 'pendiente'},
            {'address': 'B', 'lat': 40.1, 'lng': -3.1, 'prioridad': 'alta', 'estado': 'pendiente'},
            {'address': 'C', 'lat': 40.2, 'lng': -3.2, 'prioridad': 'media', 'estado': 'pendiente'},
        ]

    def test_priorizar_antes_19_nearest_neighbor(self):
        """Antes de las 19:00 el orden es nearest-neighbor (no por prioridad)."""
        paradas = self._paradas()
        ordenadas = repartidor.priorizar_paradas(paradas, modo='moto', hora_actual=10)
        # B es el primero porque es el más cercano a A (primer elemento sin origen)
        self.assertIsInstance(ordenadas, list)
        self.assertEqual(len(ordenadas), 3)

    def test_priorizar_a_las_19_prioridad_primero(self):
        """A las 19:00 las paradas de alta prioridad deben aparecer primero."""
        paradas = self._paradas()
        ordenadas = repartidor.priorizar_paradas(paradas, modo='moto', hora_actual=19)
        prioridades = [p['prioridad'] for p in ordenadas]
        # alta debe ir antes que media y baja
        self.assertEqual(prioridades[0], 'alta')

    def test_priorizar_despues_19_alta_media_baja(self):
        """A las 20:00 el orden debe ser alta > media > baja."""
        paradas = self._paradas()
        ordenadas = repartidor.priorizar_paradas(paradas, modo='coche', hora_actual=20)
        prioridades = [p['prioridad'] for p in ordenadas]
        orden_esperado = sorted(prioridades, key=lambda p: {'alta': 0, 'media': 1, 'baja': 2}[p])
        self.assertEqual(prioridades, orden_esperado)

    def test_modo_invalido_usa_moto(self):
        """Modo desconocido debe tratarse como 'moto' sin error."""
        paradas = self._paradas()
        ordenadas = repartidor.priorizar_paradas(paradas, modo='bicicleta', hora_actual=10)
        self.assertEqual(len(ordenadas), 3)

    def test_paradas_vacias(self):
        self.assertEqual(repartidor.priorizar_paradas([], hora_actual=19), [])


class AsignarPrioridadTests(unittest.TestCase):
    def test_asignar_prioridad_normaliza_valor(self):
        parada = {'address': 'X'}
        resultado = repartidor.asignar_prioridad(parada, 'ALTA')
        self.assertEqual(resultado['prioridad'], 'alta')

    def test_asignar_prioridad_valor_invalido_usa_media(self):
        parada = {'address': 'Y'}
        resultado = repartidor.asignar_prioridad(parada, 'urgente')
        self.assertEqual(resultado['prioridad'], 'media')

    def test_asignar_prioridad_no_dict_devuelve_original(self):
        resultado = repartidor.asignar_prioridad('no-dict', 'alta')
        self.assertEqual(resultado, 'no-dict')

    def test_creacion_parada_con_prioridad_alta(self):
        parada = {'address': 'Z', 'lat': 1.0, 'lng': 2.0, 'estado': 'pendiente'}
        repartidor.asignar_prioridad(parada, 'alta')
        self.assertEqual(parada['prioridad'], 'alta')


class EliminarParadaTests(unittest.TestCase):
    def test_eliminar_parada_indice_valido(self):
        paradas = [{'address': 'A'}, {'address': 'B'}, {'address': 'C'}]
        resultado = repartidor.eliminar_parada(paradas, 1)
        self.assertTrue(resultado)
        self.assertEqual(len(paradas), 2)
        self.assertEqual(paradas[0]['address'], 'A')
        self.assertEqual(paradas[1]['address'], 'C')

    def test_eliminar_parada_indice_invalido(self):
        paradas = [{'address': 'A'}]
        resultado = repartidor.eliminar_parada(paradas, 5)
        self.assertFalse(resultado)
        self.assertEqual(len(paradas), 1)


class ModoTransporteTests(unittest.TestCase):
    def _paradas_con_coords(self):
        return [
            {'address': 'A', 'lat': 40.0, 'lng': -3.0, 'prioridad': 'media', 'estado': 'pendiente'},
            {'address': 'B', 'lat': 41.0, 'lng': -4.0, 'prioridad': 'media', 'estado': 'pendiente'},
        ]

    def test_cambio_modo_recalcula_ruta(self):
        paradas = self._paradas_con_coords()
        url_moto = repartidor.generar_ruta_maps(
            paradas, modo='moto', hora_actual=10,
            origen_lat=39.9, origen_lng=-2.9,
        )
        url_pie = repartidor.generar_ruta_maps(
            paradas, modo='pie', hora_actual=10,
            origen_lat=39.9, origen_lng=-2.9,
        )
        self.assertIn('travelmode=driving', url_moto)
        self.assertIn('travelmode=walking', url_pie)
        self.assertIn('origin=39.9,-2.9', url_moto)
        self.assertIn('destination=39.9,-2.9', url_moto)

    def test_generar_ruta_sin_paradas(self):
        self.assertEqual(repartidor.generar_ruta_maps([], modo='moto'), 'No hay paradas')

    def test_generar_ruta_sin_coordenadas_validas(self):
        paradas = [{'address': 'X', 'prioridad': 'media'}]
        resultado = repartidor.generar_ruta_maps(
            paradas, modo='coche', hora_actual=10,
            origen_lat=40.0, origen_lng=-3.0,
        )
        self.assertIn('paradas sin coordenadas válidas', resultado)

    def test_generar_ruta_bloquea_origen_invalido(self):
        resultado = repartidor.generar_ruta_maps(
            self._paradas_con_coords(), modo='coche', hora_actual=10
        )
        self.assertIn('ubicación de origen válida', resultado)

    def test_coordenadas_validan_rangos_y_booleanos(self):
        self.assertTrue(repartidor.coordenadas_validas(40.4, -3.7))
        self.assertFalse(repartidor.coordenadas_validas(True, -3.7))
        self.assertFalse(repartidor.coordenadas_validas(91, -3.7))
        self.assertFalse(repartidor.coordenadas_validas(40.4, float('nan')))


class PrioridadColorTests(unittest.TestCase):
    def test_mapeo_centralizado_rojo_naranja_verde(self):
        self.assertEqual(repartidor.PRIORITY_ORDER, ('alta', 'media', 'baja'))
        self.assertEqual(repartidor.PRIORITY_COLORS['alta'], (1.0, 0.0, 0.0, 1.0))
        self.assertEqual(repartidor.PRIORITY_COLORS['media'], (1.0, 0.6, 0.0, 1.0))
        self.assertEqual(repartidor.PRIORITY_COLORS['baja'], (0.0, 1.0, 0.0, 1.0))


class ParadasV2Tests(unittest.TestCase):
    def test_completar_datos_parada_aplica_defaults_v2(self):
        parada = repartidor.completar_datos_parada({'address': 'Calle A', 'lat': 1.0, 'lng': 2.0})
        self.assertEqual(parada['paqueteria'], 'Otra')
        self.assertEqual(parada['ubicacion_vehiculo'], 'En medio')
        self.assertEqual(parada['tamaño_paquete'], 'Mediano')
        self.assertEqual(parada['tipo_operacion'], 'Entrega')
        self.assertEqual(parada['metodo_captura'], 'manual')

    def test_priorizar_mantiene_realizadas_en_historial(self):
        paradas = [
            {'address': 'Pendiente', 'lat': 40.0, 'lng': -3.0, 'prioridad': 'media', 'estado': 'pendiente'},
            {'address': 'Realizada', 'lat': 40.1, 'lng': -3.1, 'prioridad': 'alta', 'estado': 'realizada'},
        ]
        ordenadas = repartidor.priorizar_paradas(paradas, hora_actual=19, origen_lat=39.9, origen_lng=-2.9)
        self.assertEqual(ordenadas[0]['address'], 'Pendiente')
        self.assertEqual(ordenadas[-1]['estado'], 'realizada')

    def test_generar_ruta_ignora_realizadas_y_resumen_muestra_tiempo(self):
        paradas = [
            {
                'address': 'A',
                'lat': 40.0,
                'lng': -3.0,
                'prioridad': 'media',
                'estado': 'pendiente',
                'paqueteria': 'Amazon',
                'ubicacion_vehiculo': 'Delante',
                'tamaño_paquete': 'Pequeño',
                'tipo_operacion': 'Entrega',
            },
            {
                'address': 'B',
                'lat': 40.2,
                'lng': -3.2,
                'prioridad': 'alta',
                'estado': 'realizada',
                'paqueteria': 'Adidas',
                'ubicacion_vehiculo': 'Atrás',
                'tamaño_paquete': 'Grande',
                'tipo_operacion': 'Recogida',
            },
        ]
        url = repartidor.generar_ruta_maps(paradas, origen_lat=39.9, origen_lng=-2.9)
        resumen = repartidor.generar_resumen_ruta(paradas, origen_lat=39.9, origen_lng=-2.9)
        self.assertIn('waypoints=40.0,-3.0', url)
        self.assertNotIn('40.2,-3.2', url)
        self.assertIn('min estimados', resumen)
        self.assertIn('Amazon', resumen)


class AndroidManifestHookTests(unittest.TestCase):
    def test_provider_se_inserta_como_hijo_de_application_una_vez(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / 'AndroidManifest.xml'
            manifest.write_text(
                '<manifest><application></application></manifest>',
                encoding='utf-8',
            )
            p4a_hook.inject_file_provider(manifest)
            p4a_hook.inject_file_provider(manifest)
            resultado = manifest.read_text(encoding='utf-8')

        self.assertEqual(resultado.count(p4a_hook.PROVIDER_MARKER), 1)
        self.assertLess(resultado.index('<provider'), resultado.index('</application>'))

    def test_query_camara_es_hijo_de_manifest_e_idempotente(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / 'AndroidManifest.xml'
            manifest.write_text(
                '<manifest><application></application></manifest>',
                encoding='utf-8',
            )
            p4a_hook.patch_manifest(manifest)
            p4a_hook.patch_manifest(manifest)
            resultado = manifest.read_text(encoding='utf-8')

        self.assertEqual(resultado.count(p4a_hook.CAMERA_ACTION), 1)
        self.assertLess(resultado.index('<queries>'), resultado.index('<application'))
        self.assertGreater(resultado.index('<provider'), resultado.index('<application'))
        self.assertLess(resultado.index('<provider'), resultado.index('</application>'))


class PermisosGeolocalTests(unittest.TestCase):
    @patch('repartidor._is_android', return_value=False)
    def test_permiso_no_android_devuelve_true(self, _mock):
        resultado = repartidor.solicitar_permiso_geolocalizacion()
        self.assertTrue(resultado)

    @patch('repartidor._is_android', return_value=True)
    def test_permiso_android_sin_libreria_devuelve_false(self, _mock):
        # Sin la librería android.permissions disponible en entorno de test
        resultado = repartidor.solicitar_permiso_geolocalizacion()
        self.assertFalse(resultado)


class AndroidServicesTests(unittest.TestCase):
    def test_import_android_services_en_escritorio(self):
        self.assertFalse(android_services.is_android())

    @patch('android_services.is_android', return_value=False)
    def test_ubicacion_habilitada_en_escritorio(self, _mock):
        self.assertTrue(android_services.is_location_enabled())

    @patch('android_services.is_android', return_value=True)
    def test_camara_inicia_intent_desde_mactivity(self, _mock):
        bound_callbacks = {}
        activity_bridge = types.SimpleNamespace(
            bind=lambda **callbacks: bound_callbacks.update(callbacks),
            unbind=lambda **_callbacks: None,
        )
        java_activity = MagicMock()
        java_activity.getPackageName.return_value = 'org.test.repartidorapp'
        java_activity.getPackageManager.return_value = object()

        class FakeIntent:
            FLAG_GRANT_READ_URI_PERMISSION = 1
            FLAG_GRANT_WRITE_URI_PERMISSION = 2

            def __init__(self, _action):
                self.extras = {}

            def putExtra(self, key, value):
                self.extras[key] = value

            def setClipData(self, _clip):
                return None

            def addFlags(self, _flags):
                return None

            def resolveActivity(self, _manager):
                return object()

        fake_classes = {
            'android.content.ClipData': types.SimpleNamespace(
                newRawUri=lambda _label, uri: uri
            ),
            'java.io.File': lambda path: path,
            'androidx.core.content.FileProvider': types.SimpleNamespace(
                getUriForFile=lambda _activity, _authority, _file: 'content://capture'
            ),
            'android.content.Intent': FakeIntent,
            'android.provider.MediaStore': types.SimpleNamespace(
                ACTION_IMAGE_CAPTURE='android.media.action.IMAGE_CAPTURE',
                EXTRA_OUTPUT='output',
            ),
        }
        android_module = types.ModuleType('android')
        android_module.activity = activity_bridge
        android_module.mActivity = java_activity
        jnius_module = types.ModuleType('jnius')
        jnius_module.autoclass = lambda name: fake_classes[name]
        jnius_module.cast = lambda _class_name, value: value

        try:
            with tempfile.TemporaryDirectory() as tmp, patch.dict(
                sys.modules,
                {'android': android_module, 'jnius': jnius_module},
            ):
                android_services.capture_photo(
                    str(Path(tmp) / 'capture.jpg'),
                    lambda _path: None,
                    self.fail,
                )
            self.assertIn('on_activity_result', bound_callbacks)
            java_activity.startActivityForResult.assert_called_once()
            self.assertEqual(
                java_activity.startActivityForResult.call_args.args[1],
                android_services.CAMERA_REQUEST_CODE,
            )
        finally:
            android_services._camera_callback = None

    def test_permisos_denegados_incluye_respuestas_ausentes(self):
        permisos = ['coarse', 'fine', 'camera']
        self.assertEqual(
            android_services.denied_permissions(permisos, [True, False]),
            ['fine', 'camera'],
        )

    def test_ubicacion_aproximada_es_suficiente(self):
        self.assertTrue(
            android_services.has_location_permission(
                ['android.permission.ACCESS_FINE_LOCATION']
            )
        )

    def test_ubicacion_totalmente_denegada(self):
        self.assertFalse(
            android_services.has_location_permission(
                list(android_services.LOCATION_PERMISSIONS)
            )
        )

    @patch('android_services.is_android', return_value=False)
    def test_permisos_no_android_responde_sin_solicitar(self, _mock):
        resultado = []
        android_services.request_runtime_permissions(
            android_services.CAMERA_PERMISSIONS,
            lambda concedido, denegados: resultado.append((concedido, denegados)),
        )
        self.assertEqual(resultado, [(True, [])])

    @patch('android_services.is_android', return_value=True)
    def test_solicitud_interrumpida_no_concede_permiso(self, _mock):
        android_module = types.ModuleType('android')
        permissions_module = types.ModuleType('android.permissions')
        permissions_module.check_permission = lambda _permission: False
        permissions_module.request_permissions = (
            lambda _permissions, callback: callback([], [])
        )
        android_module.permissions = permissions_module
        resultado = []
        with patch.dict(
            sys.modules,
            {
                'android': android_module,
                'android.permissions': permissions_module,
            },
        ):
            android_services.request_runtime_permissions(
                android_services.CAMERA_PERMISSIONS,
                lambda concedido, denegados: resultado.append(
                    (concedido, denegados)
                ),
            )
        self.assertEqual(
            resultado,
            [(False, list(android_services.CAMERA_PERMISSIONS))],
        )


class OcrDireccionTests(unittest.TestCase):
    def test_extrae_direccion_y_codigo_postal(self):
        direccion, cp = repartidor.extraer_direccion_texto_ocr(
            'Entrega para Calle Mayor 15, 28013 Madrid'
        )
        self.assertTrue(direccion.startswith('Calle Mayor 15'))
        self.assertEqual(cp, '28013')

    def test_texto_ocr_vacio(self):
        self.assertEqual(repartidor.extraer_direccion_texto_ocr('  '), ('', ''))


class BuscarDireccionTests(unittest.TestCase):
    def test_buscar_texto_vacio_devuelve_none(self):
        self.assertIsNone(repartidor.buscar_direccion_texto(''))

    def test_buscar_texto_none_devuelve_none(self):
        self.assertIsNone(repartidor.buscar_direccion_texto(None))

    @patch('repartidor.requests')
    @patch('repartidor.API_KEY', 'TEST_KEY')
    def test_buscar_direccion_respuesta_ok(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            'status': 'OK',
            'results': [{
                'geometry': {'location': {'lat': 40.4, 'lng': -3.7}},
                'formatted_address': 'Madrid, España',
            }]
        }
        mock_requests.get.return_value = mock_resp
        parada = repartidor.buscar_direccion_texto('Madrid')
        self.assertIsNotNone(parada)
        self.assertEqual(parada['address'], 'Madrid, España')
        self.assertEqual(parada['estado'], 'pendiente')

    @patch('repartidor.requests')
    @patch('repartidor.API_KEY', 'TEST_KEY')
    def test_buscar_direccion_respuesta_sin_resultados(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {'status': 'ZERO_RESULTS', 'results': []}
        mock_requests.get.return_value = mock_resp
        parada = repartidor.buscar_direccion_texto('LugarImaginario XYZ')
        self.assertIsNone(parada)


class ReglaHoraria19Tests(unittest.TestCase):
    """Pruebas específicas para la regla de priorización a las 19:00."""

    def test_antes_19_no_aplica_prioridad_estricta(self):
        paradas = [
            {'address': 'Baja', 'lat': 40.0, 'lng': -3.0, 'prioridad': 'baja'},
            {'address': 'Alta', 'lat': 40.5, 'lng': -3.5, 'prioridad': 'alta'},
        ]
        # Antes de las 19:00: el orden depende de nearest-neighbor, no de prioridad
        result_18 = repartidor.priorizar_paradas(paradas, hora_actual=18)
        result_19 = repartidor.priorizar_paradas(paradas, hora_actual=19)
        # A las 19:00, alta debe ser primero
        self.assertEqual(result_19[0]['prioridad'], 'alta')
        # Los resultados pueden diferir entre 18:00 y 19:00
        prioridades_19 = [p['prioridad'] for p in result_19]
        self.assertEqual(prioridades_19[0], 'alta')

    def test_regla_19_grupos_optimizados(self):
        """Dentro de cada grupo de prioridad se aplica nearest-neighbor."""
        paradas = [
            {'address': 'A1', 'lat': 40.0, 'lng': -3.0, 'prioridad': 'alta'},
            {'address': 'A2', 'lat': 40.1, 'lng': -3.1, 'prioridad': 'alta'},
            {'address': 'B1', 'lat': 41.0, 'lng': -4.0, 'prioridad': 'baja'},
        ]
        result = repartidor.priorizar_paradas(paradas, hora_actual=19)
        # Primero deben salir las dos de alta
        self.assertEqual(result[0]['prioridad'], 'alta')
        self.assertEqual(result[1]['prioridad'], 'alta')
        self.assertEqual(result[2]['prioridad'], 'baja')


class LegacyCompatTests(unittest.TestCase):
    """Pruebas de compatibilidad con funciones pre-existentes."""

    def test_imports_main_module(self):
        self.assertTrue(hasattr(main, 'RepartidorApp'))

    def test_procesar_imagen_sin_archivo_devuelve_vacios(self):
        direccion, cp = repartidor.procesar_imagen('archivo_inexistente.jpg')
        self.assertEqual(direccion, '')
        self.assertEqual(cp, '')

    def test_generar_ruta_maps_sin_paradas(self):
        self.assertEqual(repartidor.generar_ruta_maps([], modo='moto'), 'No hay paradas')

    def test_priorizar_paradas_orden_correcto_hora_19(self):
        """Compatibilidad: alta primero a las 19:00."""
        paradas = [
            {'address': 'A', 'lat': 1.0, 'lng': 1.0, 'prioridad': 'baja'},
            {'address': 'B', 'lat': 1.1, 'lng': 1.1, 'prioridad': 'alta'},
            {'address': 'C', 'lat': 1.2, 'lng': 1.2, 'prioridad': 'media'},
        ]
        ordenadas = repartidor.priorizar_paradas(paradas, modo='moto', hora_actual=19)
        self.assertEqual(ordenadas[0]['prioridad'], 'alta')


class MainAppV2Tests(unittest.TestCase):
    @patch('repartidor.buscar_direccion_texto')
    def test_geocodificar_y_añadir_guarda_metadatos_de_paquete(self, mock_buscar):
        mock_buscar.return_value = {'address': 'Madrid', 'lat': 40.4, 'lng': -3.7}
        app = main.RepartidorApp()
        app._paqueteria = 'Amazon'
        app._ubicacion_paquete = 'Delante'
        app._tamaño_paquete = 'Pequeño'
        app._tipo_operacion = 'Recogida'
        app._notificacion = 'SMS'
        app._refrescar_lista = lambda: None

        app._geocodificar_y_añadir('Madrid', metodo_captura='cámara')

        self.assertEqual(len(app.lista_paradas), 1)
        parada = app.lista_paradas[0]
        self.assertEqual(parada['paqueteria'], 'Amazon')
        self.assertEqual(parada['ubicacion_vehiculo'], 'Delante')
        self.assertEqual(parada['tamaño_paquete'], 'Pequeño')
        self.assertEqual(parada['tipo_operacion'], 'Recogida')
        self.assertEqual(parada['notificacion'], 'SMS')
        self.assertEqual(parada['metodo_captura'], 'cámara')


if __name__ == '__main__':
    unittest.main()
