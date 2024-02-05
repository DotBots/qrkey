"""Crypto functions for MQTT with crypto mode."""

# SPDX-FileCopyrightText: 2024-present Alexandre Abadie <alexandre.abadie@inria.fr>
#
# SPDX-License-Identifier: BSD-3-Clause

import base64
import secrets
import string
from typing import Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from joserfc import jwe
from semver import VersionInfo

from qrkey.__about__ import __version__
from qrkey.settings import qrkey_settings


JOSE_PROTECTED = {'alg': 'dir', 'enc': 'A256GCM'}


def _parsed_version(version) -> str:
    parsed = VersionInfo.parse(version)
    # remove the patch version from the version
    return f'{parsed.major}.{parsed.minor}'


def generate_pin_code(length: int = qrkey_settings.pin_code_length) -> str:
    return ''.join(secrets.choice(string.digits) for i in range(length))


def derive_topic(pin_code: str) -> str:
    """Derive a topic from a pin code."""
    kdf_topic = HKDF(
        algorithm=hashes.SHA256(),
        length=16,
        salt=b'',
        info=f'secret_topic_{_parsed_version(__version__)}'.encode(),
    )
    topic = kdf_topic.derive(pin_code.encode())
    return base64.urlsafe_b64encode(topic).decode()


def derive_aes_key(pin_code: str) -> bytes:
    """Derive an AES key from a pin code."""
    kdf_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b'',
        info=f'secret_key_{_parsed_version(__version__)}'.encode(),
    )
    return kdf_key.derive(pin_code.encode())


def encrypt(data: str, key: bytes) -> str:
    """Encrypt data with AES-GCM."""
    return jwe.encrypt_compact(JOSE_PROTECTED, data, key)


def decrypt(data: str, key: bytes) -> Optional[str]:
    """Decrypt data with AES-GCM."""
    try:
        plain = jwe.decrypt_compact(data, key).plaintext
    except ValueError:
        plain = None
    if plain is None:
        return None
    return plain.decode()
