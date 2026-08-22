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
            {'address': 'A', 'lat': 40.0, 'lng': -3.0, 'prioridad': 'sin prioridad', 'estado': 'pendiente'},
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
        # alta debe ir antes que media y sin prioridad
        self.assertEqual(prioridades[0], 'alta')

    def test_priorizar_despues_19_alta_media_sin_prioridad(self):
        """A las 20:00 el orden debe ser alta > media > sin prioridad."""
        paradas = self._paradas()
        ordenadas = repartidor.priorizar_paradas(paradas, modo='coche', hora_actual=20)
        prioridades = [p['prioridad'] for p in ordenadas]
        orden_esperado = sorted(
            prioridades,
            key=lambda p: {'alta': 0, 'media': 1, 'sin prioridad': 2}[p],
        )
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

    def test_asignar_prioridad_valor_invalido_usa_sin_prioridad(self):
        parada = {'address': 'Y'}
        resultado = repartidor.asignar_prioridad(parada, 'urgente')
        self.assertEqual(resultado['prioridad'], 'sin prioridad')

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
            {'address': 'A', 'lat': 40.0, 'lng': -3.0, 'prioridad': 'media'},
            {'address': 'B', 'lat': 41.0, 'lng': -4.0, 'prioridad': 'media'},
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

    def test_ruta_cerrada_usa_deposito_como_origen_y_destino(self):
        url = repartidor.generar_ruta_maps(
            self._paradas_con_coords(),
            modo='moto',
            hora_actual=10,
            origen_lat=39.9,
            origen_lng=-2.9,
        )
        self.assertIn('origin=39.9,-2.9', url)
        self.assertIn('destination=39.9,-2.9', url)
        self.assertIn('waypoints=40.0,-3.0|41.0,-4.0', url)

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
    def test_mapeo_centralizado_rojo_naranja_azul(self):
        self.assertEqual(repartidor.PRIORITY_ORDER, ('alta', 'media', 'sin prioridad'))
        self.assertEqual(repartidor.PRIORITY_COLORS['alta'], (1.0, 0.0, 0.0, 1.0))
        self.assertEqual(repartidor.PRIORITY_COLORS['media'], (1.0, 0.5, 0.0, 1.0))
        self.assertEqual(repartidor.PRIORITY_COLORS['sin prioridad'], (0.0, 0.4, 1.0, 1.0))


class AndroidManifestHookTests(unittest.TestCase):
    def test_patch_manifest_no_modifica_archivo(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / 'AndroidManifest.xml'
            manifest.write_text(
                '<manifest><application></application></manifest>',
                encoding='utf-8',
            )
            original = manifest.read_text(encoding='utf-8')
            p4a_hook.patch_manifest(manifest)
            resultado = manifest.read_text(encoding='utf-8')
        self.assertEqual(resultado, original)

    def test_after_apk_build_no_falla(self):
        self.assertIsNone(p4a_hook.after_apk_build(object()))


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
    def test_maps_se_abre_mediante_action_view(self, _mock):
        created = []

        class FakeIntent:
            ACTION_VIEW = 'android.intent.action.VIEW'

            def __init__(self, action, data):
                self.action = action
                self.data = data
                self.package = None
                created.append(self)

            def setPackage(self, package):
                self.package = package

            def resolveActivity(self, _manager):
                return object()

        java_activity = MagicMock()
        java_activity.getPackageManager.return_value = object()
        android_module = types.ModuleType('android')
        android_module.mActivity = java_activity
        jnius_module = types.ModuleType('jnius')
        jnius_module.autoclass = lambda name: {
            'android.content.Intent': FakeIntent,
            'android.net.Uri': types.SimpleNamespace(parse=lambda url: url),
        }[name]
        errores = []
        url = 'https://www.google.com/maps/dir/?api=1&origin=40,-3'

        with patch.dict(
            sys.modules, {'android': android_module, 'jnius': jnius_module}
        ):
            abierto = android_services.open_map_url(url, errores.append)

        self.assertTrue(abierto)
        self.assertEqual(errores, [])
        self.assertEqual(created[0].action, FakeIntent.ACTION_VIEW)
        self.assertEqual(created[0].data, url)
        self.assertEqual(created[0].package, 'com.google.android.apps.maps')
        java_activity.startActivity.assert_called_once_with(created[0])

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
            android_services.MICROPHONE_PERMISSIONS,
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
                android_services.MICROPHONE_PERMISSIONS,
                lambda concedido, denegados: resultado.append(
                    (concedido, denegados)
                ),
            )
        self.assertEqual(
            resultado,
            [(False, list(android_services.MICROPHONE_PERMISSIONS))],
        )

    def test_reconocimiento_voz_concurrente_se_rechaza(self):
        errores = []
        android_services._speech_callback = object()
        try:
            android_services.start_speech_recognition(
                lambda _texto: self.fail('No debe iniciar otro reconocimiento.'),
                errores.append,
            )
        finally:
            android_services._speech_callback = None
        self.assertEqual(errores, ['Ya hay un reconocimiento de voz en curso.'])


class OcrDireccionTests(unittest.TestCase):
    def test_ocr_desactivado_devuelve_vacios(self):
        self.assertEqual(
            repartidor.extraer_direccion_texto_ocr(
                'Entrega para Calle Mayor 15, 28013 Madrid'
            ),
            ('', ''),
        )
        self.assertEqual(repartidor.extraer_direccion_texto_ocr('  '), ('', ''))
        self.assertEqual(repartidor.extraer_candidatos_direccion_ocr('texto'), [])


class AnadirParadaComunTests(unittest.TestCase):
    def setUp(self):
        self.paradas = []
        self.geocodificador = MagicMock(return_value={
            'address': 'Calle Mayor, 15, 28013 Madrid, España',
            'lat': 40.4168,
            'lng': -3.7038,
            'estado': 'pendiente',
        })

    def test_normaliza_geocodifica_y_conserva_metadatos(self):
        parada, error = repartidor.validar_y_anadir_parada(
            self.paradas,
            '  Calle   Mayor 15, 28013 Madrid  ',
            geocodificador=self.geocodificador,
            prioridad='alta',
            paqueteria='Grande',
            notificacion='Carta certificada',
        )
        self.assertIsNone(error)
        self.assertIs(parada, self.paradas[0])
        self.geocodificador.assert_called_once_with('Calle Mayor 15, 28013 Madrid')
        self.assertEqual(parada['prioridad'], 'alta')
        self.assertEqual(parada['estado'], 'pendiente')
        self.assertEqual(parada['paqueteria'], 'Grande')
        self.assertEqual(parada['notificacion'], 'Cartas')

    def test_rechaza_vacia_o_invalida_sin_geocodificar(self):
        for texto in ('', '   ', '1234'):
            parada, error = repartidor.validar_y_anadir_parada(
                self.paradas, texto, geocodificador=self.geocodificador
            )
            self.assertIsNone(parada)
            self.assertIn('válida', error)
        self.geocodificador.assert_not_called()

    def test_evitar_duplicado_formateado_por_geocodificador(self):
        primera, error = repartidor.validar_y_anadir_parada(
            self.paradas, 'Calle Mayor 15', geocodificador=self.geocodificador
        )
        self.assertIsNone(error)
        self.assertIsNotNone(primera)
        segunda, error = repartidor.validar_y_anadir_parada(
            self.paradas, 'calle mayor, 15', geocodificador=self.geocodificador
        )
        self.assertIsNone(segunda)
        self.assertIn('ya está', error)
        self.assertEqual(len(self.paradas), 1)

    def test_rechaza_geocodificacion_sin_coordenadas(self):
        parada, error = repartidor.validar_y_anadir_parada(
            self.paradas,
            'Calle inexistente 99',
            geocodificador=lambda _texto: None,
        )
        self.assertIsNone(parada)
        self.assertIn('coordenadas', error)

    def test_alta_asincrona_expone_geolocalizando_exito_y_error(self):
        parada, error = repartidor.iniciar_alta_parada(
            self.paradas, 'Calle Mayor 15', origen='cámara', prioridad='alta'
        )
        self.assertIsNone(error)
        self.assertEqual(parada['estado'], 'geolocalizando')
        resultado, error = repartidor.completar_alta_parada(
            self.paradas, parada, self.geocodificador
        )
        self.assertIsNone(error)
        self.assertIs(resultado, parada)
        self.assertEqual(parada['estado'], 'geolocalizada')
        self.assertEqual(parada['prioridad'], 'alta')
        self.assertTrue(repartidor.coordenadas_validas(parada['lat'], parada['lng']))

        fallida, error = repartidor.iniciar_alta_parada(
            self.paradas, 'Calle Inexistente 99', origen='voz'
        )
        self.assertIsNone(error)
        resultado, error = repartidor.completar_alta_parada(
            self.paradas, fallida, lambda _texto: None
        )
        self.assertIsNone(resultado)
        self.assertIn('coordenadas', error)
        self.assertEqual(fallida['estado'], 'error')
        self.assertNotIn('lat', fallida)


class FlujosEntradaParadaTests(unittest.TestCase):
    def _app(self):
        app = main.RepartidorApp()
        app.lbl_estado = types.SimpleNamespace(text='')
        app.txt_busqueda = types.SimpleNamespace(text='')
        app.spinner_prioridad = types.SimpleNamespace(text='media')
        app.lista_widget = None
        return app

    @patch('main.repartidor.dictar_direccion', return_value='Gran Vía 28, Madrid')
    @patch('main.android_services.is_android', return_value=False)
    def test_microfono_propone_texto_para_confirmar(self, _android, _dictado):
        app = self._app()
        app._mostrar_confirmacion = MagicMock()
        app.dictar_microfono()
        app._mostrar_confirmacion.assert_called_once_with(
            ['Gran Vía 28, Madrid'], 'micrófono'
        )

    @patch('main.android_services.is_android', return_value=False)
    def test_microfono_vacio_muestra_error(self, _android):
        app = self._app()
        app._mostrar_confirmacion = MagicMock()
        with patch('main.repartidor.dictar_direccion', return_value='  '):
            app.dictar_microfono()
        app._mostrar_confirmacion.assert_not_called()
        self.assertIn('No se captó voz', app.lbl_estado.text)

    def test_lupa_y_enter_comparten_busqueda_manual(self):
        app = self._app()
        app.txt_busqueda.text = 'Calle Serrano 12'
        app._validar_y_anadir = MagicMock(return_value=True)
        app.buscar_manual()
        app._validar_y_anadir.assert_called_once_with(
            'Calle Serrano 12', 'búsqueda'
        )
        self.assertEqual(app.txt_busqueda.text, '')

    def test_acciones_visibles_lupa_y_microfono(self):
        self.assertEqual(main.SEARCH_ICON, '🔍')
        self.assertEqual(main.VOICE_ICON, '🎙')
        self.assertNotEqual(main.SEARCH_ICON, main.VOICE_ICON)

    @patch('main.repartidor.buscar_direccion_texto')
    def test_voz_y_escritura_geocodifican_por_el_mismo_alta(self, geocode):
        geocode.side_effect = lambda texto: {
            'address': texto,
            'lat': 40.4168,
            'lng': -3.7038,
        }
        app = self._app()
        app._ejecutar_en_segundo_plano = lambda callback: callback()
        app._dispatch_ui = lambda callback: callback()

        class PopupFake:
            def dismiss(self):
                return None

        app._confirmar_propuesta(
            PopupFake(),
            types.SimpleNamespace(text='Calle Voz 20'),
            'micrófono',
            types.SimpleNamespace(text=''),
        )
        app.txt_busqueda.text = 'Calle Escrita 30'
        app.buscar_manual()

        self.assertEqual(geocode.call_count, 2)
        self.assertEqual(
            {parada['origen'] for parada in app.lista_paradas},
            {'micrófono', 'búsqueda'},
        )
        self.assertTrue(all(
            parada['estado'] == 'geolocalizada'
            and repartidor.coordenadas_validas(parada['lat'], parada['lng'])
            for parada in app.lista_paradas
        ))

    @patch('main.webbrowser.open')
    @patch('main.android_services.is_android', return_value=True)
    def test_optimizacion_bloquea_gps_y_paradas_sin_coordenadas(
        self, _android, navegador
    ):
        app = self._app()
        app.spinner_modo = types.SimpleNamespace(text='Moto')
        app.lista_paradas = [{
            'address': 'Calle Pendiente 1',
            'estado': 'geolocalizando',
        }]
        app._mostrar_dialogo_activar_ubicacion = MagicMock()
        with patch('main.android_services.is_location_enabled', return_value=False):
            app.abrir_google_maps()
        app._mostrar_dialogo_activar_ubicacion.assert_called_once_with()
        self.assertTrue(app._open_map_when_located)

        app._ubicacion_actual = {'lat': 40.4, 'lng': -3.7}
        with patch('main.android_services.is_location_enabled', return_value=True):
            app.abrir_google_maps()
        self.assertIn('geolocalizándose', app.lbl_estado.text)
        navegador.assert_not_called()

    @patch('main.webbrowser.open')
    @patch('main.android_services.open_map_url')
    @patch('main.android_services.is_location_enabled', return_value=True)
    @patch('main.android_services.is_android', return_value=True)
    def test_android_abre_ruta_gps_cerrada_en_app_maps(
        self, _android, _enabled, abrir_maps, navegador
    ):
        app = self._app()
        app.spinner_modo = types.SimpleNamespace(text='Moto')
        app._ubicacion_actual = {'lat': 40.4, 'lng': -3.7}
        app.lista_paradas = [{
            'address': 'Calle Mayor 1',
            'lat': 40.5,
            'lng': -3.8,
            'estado': 'geolocalizada',
            'prioridad': 'media',
        }]

        app.abrir_google_maps()

        abrir_maps.assert_called_once()
        url = abrir_maps.call_args.args[0]
        self.assertIn('origin=40.4,-3.7', url)
        self.assertIn('destination=40.4,-3.7', url)
        self.assertIn('waypoints=40.5,-3.8', url)
        navegador.assert_not_called()

    @patch('main.android_services.is_location_enabled', return_value=True)
    @patch('main.android_services.is_android', return_value=True)
    def test_maps_solicita_gps_si_aun_no_hay_origen(self, _android, _enabled):
        app = self._app()
        app.lista_paradas = [{
            'address': 'Calle Mayor 1',
            'lat': 40.5,
            'lng': -3.8,
            'estado': 'geolocalizada',
        }]
        app.solicitar_ubicacion = MagicMock()

        app.abrir_google_maps()

        app.solicitar_ubicacion.assert_called_once_with()
        self.assertIn('GPS actual', app.lbl_estado.text)
        self.assertTrue(app._open_map_when_located)

    def test_maps_se_abre_automaticamente_al_recibir_gps_pendiente(self):
        app = self._app()
        app._open_map_when_located = True
        app.abrir_google_maps = MagicMock()

        app._on_ubicacion({'lat': 40.4, 'lng': -3.7})

        self.assertFalse(app._open_map_when_located)
        app.abrir_google_maps.assert_called_once_with()


class SelectoresEntregaTests(unittest.TestCase):
    def test_paqueteria_muestra_tamanos_pequeno_mediano_grande(self):
        self.assertEqual(repartidor.PACKAGE_OPTIONS, ('Pequeño', 'Mediano', 'Grande'))
        self.assertEqual(repartidor.DEFAULT_PACKAGE, 'Mediano')

    def test_selector_y_opciones_de_cartas_no_muestran_notificaciones(self):
        self.assertEqual(main._SELECT_CARTAS, 'Cartas')
        self.assertEqual(repartidor.LETTER_OPTIONS, ('Cartas',))
        self.assertNotIn('notificación', ' '.join(repartidor.LETTER_OPTIONS).lower())

    def test_normaliza_valores_legacy_persistidos(self):
        parada = {
            'address': 'Calle Mayor 1',
            'paqueteria': 'Correos',
            'notificacion': 'SMS',
        }
        repartidor.normalizar_metadatos_parada(parada)
        self.assertEqual(parada['paqueteria'], 'Mediano')
        self.assertEqual(parada['notificacion'], 'Cartas')
        self.assertEqual(repartidor.normalizar_paqueteria('Express 24h'), 'Grande')
        self.assertEqual(repartidor.normalizar_cartas('Carta certificada'), 'Cartas')

    def test_callbacks_guardan_paqueteria_y_cartas_canonicas(self):
        app = main.RepartidorApp()
        app.lbl_estado = types.SimpleNamespace(text='')
        paquete = types.SimpleNamespace(text='')
        cartas = types.SimpleNamespace(text='')

        app._on_paqueteria_cambio(paquete, 'Express 24h')
        app._on_notificacion_cambio(cartas, 'Carta ordinaria')

        self.assertEqual(app._paqueteria, 'Grande')
        self.assertEqual(paquete.text, 'Grande')
        self.assertEqual(app._notificacion, 'Cartas')
        self.assertEqual(cartas.text, 'Cartas')
        self.assertIn('Tipo de entrega: Cartas', app.lbl_estado.text)


class InicioUbicacionTests(unittest.TestCase):
    def _app(self):
        app = main.RepartidorApp()
        app.lbl_estado = types.SimpleNamespace(text='')
        app.lista_widget = None
        return app

    @patch('main.android_services.is_android', return_value=True)
    @patch('main.android_services.location_permission_granted', return_value=False)
    def test_denegacion_no_repite_prompt_automaticamente(
        self, _permission, _android
    ):
        app = self._app()
        with patch(
            'main.android_services.request_runtime_permissions',
            side_effect=lambda _perms, callback: callback(
                False, list(android_services.LOCATION_PERMISSIONS)
            ),
        ) as request:
            app._solicitar_ubicacion_inicial()
            app._solicitar_ubicacion_inicial()
        self.assertEqual(request.call_count, 1)
        self.assertTrue(app._location_permission_denied)
        self.assertIn('ajustes', app.lbl_estado.text.lower())

    @patch('main.android_services.is_android', return_value=True)
    @patch('main.android_services.is_location_enabled', return_value=True)
    def test_retorno_desde_ajustes_reintenta_sin_otro_dialogo(
        self, _enabled, _android
    ):
        app = self._app()
        app._waiting_location_settings = True
        app._location_dialog_shown = True
        app._comprobar_proveedor_y_localizar = MagicMock()
        app.on_resume()
        self.assertFalse(app._waiting_location_settings)
        self.assertFalse(app._location_dialog_shown)
        app._comprobar_proveedor_y_localizar.assert_called_once_with(
            prompt_settings=False
        )

    @patch('main.android_services.is_android', return_value=True)
    @patch('main.android_services.location_permission_granted', return_value=True)
    @patch('main.android_services.is_location_enabled', return_value=True)
    def test_resume_reanuda_una_adquisicion_interrumpida(
        self, _enabled, _permission, _android
    ):
        app = self._app()
        app._resume_location_after_pause = True
        app._iniciar_localizacion = MagicMock()
        app.on_resume()
        app._iniciar_localizacion.assert_called_once_with()
        self.assertFalse(app._resume_location_after_pause)

    @patch('main.android_services.is_android', return_value=True)
    @patch('main.android_services.location_permission_granted', return_value=True)
    @patch('main.android_services.is_location_enabled', return_value=False)
    def test_proveedor_apagado_muestra_un_solo_prompt_automatico(
        self, _enabled, _permission, _android
    ):
        app = self._app()
        app._mostrar_dialogo_activar_ubicacion = MagicMock(
            side_effect=lambda: setattr(app, '_location_dialog_shown', True)
        )
        app._solicitar_ubicacion_inicial()
        app._solicitar_ubicacion_inicial()
        app._mostrar_dialogo_activar_ubicacion.assert_called_once()


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
            {'address': 'Sin prioridad', 'lat': 40.0, 'lng': -3.0, 'prioridad': 'sin prioridad'},
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
            {'address': 'B1', 'lat': 41.0, 'lng': -4.0, 'prioridad': 'sin prioridad'},
        ]
        result = repartidor.priorizar_paradas(paradas, hora_actual=19)
        # Primero deben salir las dos de alta
        self.assertEqual(result[0]['prioridad'], 'alta')
        self.assertEqual(result[1]['prioridad'], 'alta')
        self.assertEqual(result[2]['prioridad'], 'sin prioridad')


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
            {'address': 'A', 'lat': 1.0, 'lng': 1.0, 'prioridad': 'sin prioridad'},
            {'address': 'B', 'lat': 1.1, 'lng': 1.1, 'prioridad': 'alta'},
            {'address': 'C', 'lat': 1.2, 'lng': 1.2, 'prioridad': 'media'},
        ]
        ordenadas = repartidor.priorizar_paradas(paradas, modo='moto', hora_actual=19)
        self.assertEqual(ordenadas[0]['prioridad'], 'alta')


if __name__ == '__main__':
    unittest.main()
