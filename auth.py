"""Gestión de autenticación local para la App Repartidor.

Las cuentas se almacenan en un fichero JSON (``users.json``) dentro del
directorio de datos de la aplicación.  Las contraseñas se guardan como
hash SHA-256 para no almacenarlas en claro.

Tipos de cuenta
---------------
- ``'trial'``: versión de prueba gratuita, máximo ``TRIAL_MAX_PARADAS`` paradas.
- ``'full'``: versión completa, sin límite de paradas.
"""

import hashlib
import json
import os

_USERS_FILENAME = 'users.json'

TRIAL_MAX_PARADAS = 15
DONATION_URL = 'https://www.buymeacoffee.com/repartidorapp'

ACCOUNT_TRIAL = 'trial'
ACCOUNT_FULL = 'full'


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


def register_user(data_dir, username, password, account_type=ACCOUNT_TRIAL):
    """Registra un nuevo usuario.

    Args:
        data_dir: Directorio donde se almacena ``users.json``.
        username: Nombre de usuario (se elimina espacios al inicio/final).
        password: Contraseña en claro.
        account_type: ``'trial'`` (defecto) o ``'full'``.

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
    if account_type not in (ACCOUNT_TRIAL, ACCOUNT_FULL):
        account_type = ACCOUNT_TRIAL

    users = _load_users(data_dir)
    if username in users:
        return False

    users[username] = {
        'password': _hash_password(password),
        'account_type': account_type,
    }
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
    entry = users.get(username)
    if entry is None:
        return False
    # Soporte para formato antiguo (solo hash como string)
    stored_hash = entry if isinstance(entry, str) else entry.get('password', '')
    return stored_hash == _hash_password(password)


def get_account_type(data_dir, username):
    """Devuelve el tipo de cuenta del usuario (``'trial'`` o ``'full'``).

    Si el usuario no existe o el campo no está presente devuelve ``'trial'``.
    """
    username = username.strip()
    users = _load_users(data_dir)
    entry = users.get(username)
    if entry is None or isinstance(entry, str):
        return ACCOUNT_TRIAL
    return entry.get('account_type', ACCOUNT_TRIAL)


def upgrade_to_full(data_dir, username):
    """Actualiza la cuenta del usuario a versión completa.

    Returns:
        ``True`` si se actualizó correctamente.
        ``False`` si el usuario no existe.
    """
    username = username.strip()
    users = _load_users(data_dir)
    if username not in users:
        return False
    entry = users[username]
    if isinstance(entry, str):
        entry = {'password': entry}
    entry['account_type'] = ACCOUNT_FULL
    users[username] = entry
    _save_users(data_dir, users)
    return True


def is_trial(data_dir, username):
    """Devuelve ``True`` si la cuenta es de tipo prueba."""
    return get_account_type(data_dir, username) == ACCOUNT_TRIAL


def user_exists(data_dir, username):
    """Devuelve ``True`` si el usuario ya está registrado."""
    return username.strip() in _load_users(data_dir)


def has_any_user(data_dir):
    """Devuelve ``True`` si existe al menos un usuario registrado."""
    return bool(_load_users(data_dir))
