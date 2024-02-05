from unittest.mock import patch

import pytest  # type: ignore

from qrkey.crypto import (
    generate_pin_code,
    encrypt,
    decrypt,
    derive_aes_key,
    derive_topic,
    _parsed_version,
)
from qrkey.settings import qrkey_settings


@pytest.mark.parametrize(
    'version,expected',
    [
        ('0.0.1', '0.0'),
        ('1.2.3', '1.2'),
        ('1.2.3-alpha', '1.2'),
    ],
)
def test_parsed_version(version, expected):
    assert _parsed_version(version) == expected


def test_generate_pin_code():
    pin_code = generate_pin_code()
    assert len(pin_code) == qrkey_settings.pin_code_length
    assert pin_code.isdigit()


@patch('qrkey.crypto._parsed_version')
def test_derive_topic(version):
    version.return_value = '0.1.1'
    topic = derive_topic('123456789123')
    assert topic == '8X4pOiPqXIC8GggBVfagwQ=='


@patch('qrkey.crypto._parsed_version')
def test_derive_aes_key(version):
    version.return_value = '0.1.1'
    key = derive_aes_key('123456789123').hex()
    assert key == '4a9d960e01246c885107eb1eeedcb412abef88c278899c6071d4997606fe9c17'


@patch('qrkey.crypto._parsed_version')
def test_encrypt(version):
    version.return_value = '0.1.1'
    key = bytes.fromhex(
        '4a9d960e01246c885107eb1eeedcb412abef88c278899c6071d4997606fe9c17'
    )
    result = encrypt('test_message', key)
    assert len(result.split('.')) == 5
    assert result.startswith('eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0')
    assert len(result) == 97


@patch('qrkey.crypto._parsed_version')
def test_decrypt(version):
    version.return_value = '0.1.1'
    key = bytes.fromhex(
        '4a9d960e01246c885107eb1eeedcb412abef88c278899c6071d4997606fe9c17'
    )
    result = decrypt(
        'eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0..DBBeusuyLXKeTPsy.Ad7UPf1DOm_z64_7.jLtrAMIWU-Mvexz5OYUxOw',
        key,
    )
    assert result == 'test_message'


@patch('qrkey.crypto._parsed_version')
def test_decrypt_none(version):
    version.return_value = '0.1.1'
    key = bytes.fromhex(
        '4a9d960e01246c885107eb1eeedcb412abef88c278899c6071d4997606fe9c17'
    )
    result = decrypt(
        'eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0..DBBeusuyLXKeTPsy.Ad7UPf1DOm_z64_7.jLtrAMIWU-Mvexz5OYU',
        key,
    )
    assert result is None
    result = decrypt(
        'eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0..DBBeusuyLXKe.Ad7UPf1DOm_z64_7.jLtrAMIWU-Mvexz5OYUxOw',
        key,
    )
    assert result is None
