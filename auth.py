"""Gestión de autenticación local para la App Repartidor.

Las cuentas se almacenan en un fichero JSON (``users.json``) dentro del
directorio de datos de la aplicación.  Las contraseñas se guardan como
hash SHA-256 para no almacenarlas en claro.
"""

import hashlib
import json
import os

_USERS_FILENAME = 'users.json'


def _users_path(data_dir):
    return os.path.join(data_dir, _USERS_FILENAME)


def _hash_password(password):
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def _load_users(data_dir):
    path = _users_path(data_dir)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def _save_users(data_dir, users):
    path = _users_path(data_dir)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(users, f, indent=2, ensure_ascii=False)


def register_user(data_dir, username, password):
    """Registra un nuevo usuario.

    Returns:
        ``True`` si el registro fue exitoso.
        ``False`` si el nombre de usuario ya existe.

    Raises:
        ValueError: Si ``username`` o ``password`` están vacíos.
    """
    username = username.strip()
    if not username:
        raise ValueError('El nombre de usuario no puede estar vacío.')
    if not password:
        raise ValueError('La contraseña no puede estar vacía.')

    users = _load_users(data_dir)
    if username in users:
        return False

    users[username] = _hash_password(password)
    _save_users(data_dir, users)
    return True


def verify_user(data_dir, username, password):
    """Comprueba las credenciales de un usuario.

    Returns:
        ``True`` si el usuario existe y la contraseña es correcta.
        ``False`` en caso contrario.
    """
    username = username.strip()
    users = _load_users(data_dir)
    hashed = users.get(username)
    if hashed is None:
        return False
    return hashed == _hash_password(password)


def user_exists(data_dir, username):
    """Devuelve ``True`` si el usuario ya está registrado."""
    return username.strip() in _load_users(data_dir)


def has_any_user(data_dir):
    """Devuelve ``True`` si existe al menos un usuario registrado."""
    return bool(_load_users(data_dir))
