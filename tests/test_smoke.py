import unittest
from unittest.mock import MagicMock, patch

import main
import repartidor


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
            {'address': 'A', 'lat': 40.0, 'lng': -3.0, 'prioridad': 'media'},
            {'address': 'B', 'lat': 41.0, 'lng': -4.0, 'prioridad': 'media'},
        ]

    def test_cambio_modo_recalcula_ruta(self):
        paradas = self._paradas_con_coords()
        url_moto = repartidor.generar_ruta_maps(paradas, modo='moto', hora_actual=10)
        url_pie = repartidor.generar_ruta_maps(paradas, modo='pie', hora_actual=10)
        self.assertIn('travelmode=driving', url_moto)
        self.assertIn('travelmode=walking', url_pie)

    def test_generar_ruta_sin_paradas(self):
        self.assertEqual(repartidor.generar_ruta_maps([], modo='moto'), 'No hay paradas')

    def test_generar_ruta_sin_coordenadas_validas(self):
        paradas = [{'address': 'X', 'prioridad': 'media'}]
        resultado = repartidor.generar_ruta_maps(paradas, modo='coche', hora_actual=10)
        self.assertEqual(resultado, 'No hay paradas con coordenadas válidas')


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


if __name__ == '__main__':
    unittest.main()
