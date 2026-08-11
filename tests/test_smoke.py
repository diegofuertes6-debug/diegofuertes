import unittest

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
