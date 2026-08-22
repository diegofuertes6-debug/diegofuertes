"""Gestión de autenticación local para la App Repartidor.

Las cuentas se almacenan en un fichero JSON (``users.json``) dentro del
directorio de datos de la aplicación.  Las contraseñas se guardan como
hash PBKDF2-HMAC-SHA256 con sal aleatoria por usuario, lo que las protege
frente a ataques de diccionario y tablas rainbow.

Tipos de cuenta
---------------
- ``'trial'``: versión de prueba gratuita, máximo ``TRIAL_MAX_PARADAS`` paradas.
- ``'full'``: versión completa, sin límite de paradas.
"""

import hashlib
import json
import os
import secrets

_USERS_FILENAME = 'users.json'

TRIAL_MAX_PARADAS = 15
DONATION_URL = 'https://www.buymeacoffee.com/repartidorapp'

ACCOUNT_TRIAL = 'trial'
ACCOUNT_FULL = 'full'

# PBKDF2 parameters
_PBKDF2_ITERATIONS = 260_000
_PBKDF2_HASH = 'sha256'
_SALT_BYTES = 32


def _users_path(data_dir):
    return os.path.join(data_dir, _USERS_FILENAME)


def _hash_password_pbkdf2(password, salt_hex=None):
    """Returns ``(hash_hex, salt_hex)`` using PBKDF2-HMAC-SHA256."""
    if salt_hex is None:
        salt = secrets.token_bytes(_SALT_BYTES)
    else:
        salt = bytes.fromhex(salt_hex)
    dk = hashlib.pbkdf2_hmac(
        _PBKDF2_HASH,
        password.encode('utf-8'),
        salt,
        _PBKDF2_ITERATIONS,
    )
    return dk.hex(), salt.hex()


def _verify_password(password, stored):
    """Verify *password* against a stored PBKDF2 credential entry.

    Only accepts the current ``{'pbkdf2': str, 'salt': str}`` format.
    Entries in any other format are rejected as invalid.
    """
    if not isinstance(stored, dict):
        return False
    pbkdf2 = stored.get('pbkdf2')
    salt = stored.get('salt')
    if not pbkdf2 or not salt:
        return False
    candidate, _ = _hash_password_pbkdf2(password, salt_hex=salt)
    return secrets.compare_digest(candidate, pbkdf2)


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

    hash_hex, salt_hex = _hash_password_pbkdf2(password)
    users[username] = {
        'pbkdf2': hash_hex,
        'salt': salt_hex,
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
    return _verify_password(password, entry)


def get_account_type(data_dir, username):
    """Devuelve el tipo de cuenta del usuario (``'trial'`` o ``'full'``).

    Si el usuario no existe o el campo no está presente devuelve ``'trial'``.
    """
    username = username.strip()
    users = _load_users(data_dir)
    entry = users.get(username)
    if not isinstance(entry, dict):
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
    if not isinstance(entry, dict):
        return False
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
