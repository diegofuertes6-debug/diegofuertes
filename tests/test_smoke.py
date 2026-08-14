import unittest
import tempfile
import os

import main
import repartidor
import auth


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


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        self.tmp.close()
        os.unlink(self.tmp.name)  # ensure it doesn't exist yet
        self.path = self.tmp.name

    def tearDown(self):
        if os.path.exists(self.path):
            os.unlink(self.path)

    def test_no_users_initially(self):
        self.assertFalse(auth.has_any_user(self.path))

    def test_register_success(self):
        ok, msg = auth.register('alice', 'secret123', self.path)
        self.assertTrue(ok)
        self.assertIn('exitoso', msg.lower())

    def test_register_empty_username(self):
        ok, msg = auth.register('', 'secret123', self.path)
        self.assertFalse(ok)
        self.assertIn('vacío', msg)

    def test_register_empty_password(self):
        ok, msg = auth.register('alice', '', self.path)
        self.assertFalse(ok)
        self.assertIn('vacía', msg)

    def test_register_duplicate_user(self):
        auth.register('alice', 'secret123', self.path)
        ok, msg = auth.register('alice', 'other', self.path)
        self.assertFalse(ok)
        self.assertIn('ya existe', msg)

    def test_login_success(self):
        auth.register('alice', 'secret123', self.path)
        ok, msg = auth.login('alice', 'secret123', self.path)
        self.assertTrue(ok)
        self.assertIn('exitoso', msg.lower())

    def test_login_wrong_password(self):
        auth.register('alice', 'secret123', self.path)
        ok, msg = auth.login('alice', 'wrong', self.path)
        self.assertFalse(ok)
        self.assertIn('incorrecta', msg.lower())

    def test_login_nonexistent_user(self):
        ok, msg = auth.login('ghost', 'pass', self.path)
        self.assertFalse(ok)
        self.assertIn('no existe', msg)

    def test_login_empty_fields(self):
        ok1, _ = auth.login('', 'pass', self.path)
        ok2, _ = auth.login('alice', '', self.path)
        self.assertFalse(ok1)
        self.assertFalse(ok2)

    def test_passwords_not_stored_plaintext(self):
        auth.register('alice', 'supersecret', self.path)
        with open(self.path, encoding='utf-8') as fh:
            raw = fh.read()
        self.assertNotIn('supersecret', raw)

    def test_has_any_user_after_register(self):
        auth.register('bob', 'pass123', self.path)
        self.assertTrue(auth.has_any_user(self.path))


if __name__ == '__main__':
    unittest.main()
