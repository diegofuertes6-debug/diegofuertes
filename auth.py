# -*- coding: utf-8 -*-
"""Módulo de autenticación básica para el proyecto Repartidor.

Almacena credenciales en un fichero JSON con contraseñas hasheadas mediante
scrypt (KDF computacionalmente costosa, resistente a ataques de fuerza bruta).
No se guardan contraseñas en texto plano.
"""
import hashlib
import json
import os
import secrets

USERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.users.json')


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _load_users(path=None):
    """Carga el diccionario de usuarios desde disco."""
    path = path or USERS_FILE
    if not os.path.isfile(path):
        return {}
    try:
        with open(path, encoding='utf-8') as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def _save_users(users, path=None):
    """Persiste el diccionario de usuarios en disco."""
    path = path or USERS_FILE
    try:
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(users, fh, indent=2, ensure_ascii=False)
    except OSError as exc:
        raise RuntimeError(f'No se pudo guardar el fichero de usuarios: {exc}') from exc


def _hash_password(password, salt=None):
    """Devuelve (salt_hex, hash_hex) usando scrypt (KDF resistente a fuerza bruta)."""
    if salt is None:
        salt = secrets.token_hex(16)
    # scrypt parameters: n=2^14, r=8, p=1 – balance entre seguridad y velocidad en local
    dk = hashlib.scrypt(
        password.encode('utf-8'),
        salt=salt.encode('utf-8'),
        n=2 ** 14,
        r=8,
        p=1,
    )
    return salt, dk.hex()


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def has_any_user(path=None):
    """Devuelve True si existe al menos un usuario registrado."""
    return bool(_load_users(path))


def register(username, password, path=None):
    """Registra un nuevo usuario.

    Returns:
        (True, 'Registro exitoso') on success.
        (False, <mensaje de error>) on failure.
    """
    username = (username or '').strip()
    password = password or ''

    if not username:
        return False, 'El nombre de usuario no puede estar vacío.'
    if not password:
        return False, 'La contraseña no puede estar vacía.'

    users = _load_users(path)
    if username in users:
        return False, f'El usuario "{username}" ya existe. Por favor inicia sesión.'

    salt, hashed = _hash_password(password)
    users[username] = {'salt': salt, 'hash': hashed}
    _save_users(users, path)
    return True, 'Registro exitoso. Ya puedes iniciar sesión.'


def login(username, password, path=None):
    """Valida credenciales.

    Returns:
        (True, 'Inicio de sesión exitoso') on success.
        (False, <mensaje de error>) on failure.
    """
    username = (username or '').strip()
    password = password or ''

    if not username:
        return False, 'El nombre de usuario no puede estar vacío.'
    if not password:
        return False, 'La contraseña no puede estar vacía.'

    users = _load_users(path)
    if username not in users:
        return False, f'El usuario "{username}" no existe. ¿Deseas registrarte?'

    record = users[username]
    _, expected_hash = _hash_password(password, salt=record['salt'])
    if expected_hash != record['hash']:
        return False, 'Contraseña incorrecta.'

    return True, 'Inicio de sesión exitoso.'


# ---------------------------------------------------------------------------
# Flujo interactivo por consola
# ---------------------------------------------------------------------------

def _prompt_credentials(prompt_user='Usuario: ', prompt_pass='Contraseña: '):
    """Solicita usuario y contraseña por consola (sin echo para la contraseña)."""
    import getpass
    username = input(prompt_user).strip()
    password = getpass.getpass(prompt_pass)
    return username, password


def run_auth_flow(path=None):
    """Ejecuta el flujo completo de autenticación por consola.

    - Si no hay usuarios registrados, ofrece registro obligatorio.
    - Si hay usuarios, pide login con opción de registrarse.
    - Repite hasta autenticar correctamente.

    Returns:
        El nombre de usuario autenticado (str).
    """
    first_time = not has_any_user(path)

    if first_time:
        print('\n=== Bienvenido a Repartidor ===')
        print('No hay usuarios registrados. Debes crear una cuenta.')

    while True:
        if first_time:
            action = 'r'
        else:
            print('\n=== Repartidor — Autenticación ===')
            print('  [1] Iniciar sesión')
            print('  [2] Registrarse')
            choice = input('Selecciona una opción (1/2): ').strip()
            action = 'r' if choice == '2' else 'l'

        if action == 'r':
            print('\n--- Registro de nueva cuenta ---')
            username, password = _prompt_credentials(
                prompt_user='Nuevo usuario: ',
                prompt_pass='Nueva contraseña: ',
            )
            ok, msg = register(username, password, path)
            print(msg)
            if ok:
                first_time = False
                # Continúa al login con las credenciales recién creadas
                ok2, msg2 = login(username, password, path)
                if ok2:
                    print(f'Bienvenido, {username}.')
                    return username
        else:
            print('\n--- Inicio de sesión ---')
            username, password = _prompt_credentials()
            ok, msg = login(username, password, path)
            print(msg)
            if ok:
                print(f'Bienvenido, {username}.')
                return username
