import unittest
from datetime import datetime

import main
import repartidor


class RepartidorSmokeTests(unittest.TestCase):
    def test_priorizar_paradas_orden_correcto(self):
        paradas = [
            {'direccion': 'A', 'prioridad': 'baja'},
            {'direccion': 'B', 'prioridad': 'alta'},
            {'direccion': 'C', 'prioridad': 'media'},
        ]

        ordenadas = repartidor.priorizar_paradas(paradas, modo='moto')
        self.assertEqual([p['direccion'] for p in ordenadas], ['B', 'C', 'A'])

    def test_asignar_prioridad_normaliza_valor(self):
        parada = {'direccion': 'X'}
        resultado = repartidor.asignar_prioridad(parada, 'ALTA')
        self.assertEqual(resultado['prioridad'], 'alta')

    def test_generar_codigo_parada_independiente_por_tipo(self):
        self.assertEqual(repartidor.generar_codigo_parada('notificacion'), 'N1')
        self.assertEqual(repartidor.generar_codigo_parada('notificacion'), 'N2')
        self.assertEqual(repartidor.generar_codigo_parada('paquete'), 'P1')
        self.assertEqual(repartidor.generar_codigo_parada('paquete'), 'P2')

    def test_priorizar_paradas_a_las_18_30_usa_grupos_por_prioridad(self):
        paradas = [
            {'direccion': 'A', 'lat': 40.0, 'lng': 0.0, 'prioridad': 'baja', 'pendiente': True},
            {'direccion': 'B', 'lat': 40.0, 'lng': 1.0, 'prioridad': 'alta', 'pendiente': True},
            {'direccion': 'C', 'lat': 39.0, 'lng': 0.0, 'prioridad': 'media', 'pendiente': True},
            {'direccion': 'D', 'lat': 41.0, 'lng': 0.0, 'prioridad': 'alta', 'pendiente': False},
        ]

        ordenadas = repartidor.priorizar_paradas(paradas, modo='moto', hora=datetime(2026, 1, 1, 18, 30))
        self.assertEqual([p['direccion'] for p in ordenadas], ['B', 'C', 'A'])

    def test_optimizar_ruta_sin_prioridad_usa_distancia(self):
        paradas = [
            {'direccion': 'A', 'lat': 40.0, 'lng': 0.0},
            {'direccion': 'B', 'lat': 40.0, 'lng': 0.5},
            {'direccion': 'C', 'lat': 40.5, 'lng': 0.0},
        ]

        ordenadas = repartidor.ordenar_ruta_optima(paradas)
        self.assertEqual([p['direccion'] for p in ordenadas], ['A', 'B', 'C'])

    def test_imports_main_module(self):
        self.assertTrue(hasattr(main, 'RepartidorApp'))

    def test_procesar_imagen_sin_archivo_devuelve_vacios(self):
        direccion, cp = repartidor.procesar_imagen('archivo_inexistente.jpg')
        self.assertEqual(direccion, '')
        self.assertEqual(cp, '')

    def test_generar_ruta_maps_sin_paradas(self):
        self.assertEqual(repartidor.generar_ruta_maps([], modo='moto'), 'No hay paradas')


if __name__ == '__main__':
    unittest.main()
