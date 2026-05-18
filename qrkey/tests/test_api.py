# SPDX-FileCopyrightText: 2024-present Alexandre Abadie <alexandre.abadie@inria.fr>
#
# SPDX-License-Identifier: BSD-3-Clause

import asyncio
import io
import os
import subprocess
import sys
from unittest.mock import MagicMock

import pytest  # type: ignore
import segno

from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from qrkey.api import api
from qrkey.models import (
    MqttPinCodeModel,
)
from qrkey.settings import qrkey_settings


client = AsyncClient(transport=ASGITransport(app=api), base_url='http://testserver')

TEST_PIN_CODE = '123456789123'


@pytest.fixture(autouse=True)
def controller():
    api.controller = MagicMock()
    api.controller.pin_code = TEST_PIN_CODE
    api.controller.websockets = []


@pytest.mark.asyncio
async def test_openapi_exists():
    response = await client.get('/api')
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_pin_code():
    response = await client.get('/pin_code')
    assert response.status_code == 200
    assert response.json() == MqttPinCodeModel(pin=TEST_PIN_CODE).model_dump()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'version,use_ssl,username,password,url',
    [
        pytest.param(
            qrkey_settings.mqtt_version,
            qrkey_settings.mqtt_use_ssl,
            qrkey_settings.mqtt_username,
            qrkey_settings.mqtt_password,
            (
                f'{qrkey_settings.frontend_base_url}?use_qrkey=true'
                f'&pin={TEST_PIN_CODE}'
                f'&mqtt_host={qrkey_settings.mqtt_host}'
                f'&mqtt_port={qrkey_settings.mqtt_ws_port}'
                f'&mqtt_version={qrkey_settings.mqtt_version}'
                f'&mqtt_use_ssl={qrkey_settings.mqtt_use_ssl}'
            ),
            id='Default',
        ),
        pytest.param(
            qrkey_settings.mqtt_version,
            qrkey_settings.mqtt_use_ssl,
            'test_user',
            'test_password',
            (
                f'{qrkey_settings.frontend_base_url}?use_qrkey=true'
                f'&pin={TEST_PIN_CODE}'
                f'&mqtt_host={qrkey_settings.mqtt_host}'
                f'&mqtt_port={qrkey_settings.mqtt_ws_port}'
                f'&mqtt_version={qrkey_settings.mqtt_version}'
                f'&mqtt_use_ssl={qrkey_settings.mqtt_use_ssl}'
                '&mqtt_username=test_user'
                '&mqtt_password=test_password'
            ),
            id='UsernameSet',
        ),
        pytest.param(
            4,
            qrkey_settings.mqtt_use_ssl,
            None,
            None,
            (
                f'{qrkey_settings.frontend_base_url}?use_qrkey=true'
                f'&pin={TEST_PIN_CODE}'
                f'&mqtt_host={qrkey_settings.mqtt_host}'
                f'&mqtt_port={qrkey_settings.mqtt_ws_port}'
                '&mqtt_version=4'
                f'&mqtt_use_ssl={qrkey_settings.mqtt_use_ssl}'
            ),
            id='VersionSet',
        ),
        pytest.param(
            qrkey_settings.mqtt_version,
            True,
            None,
            None,
            (
                f'{qrkey_settings.frontend_base_url}?use_qrkey=true'
                f'&pin={TEST_PIN_CODE}'
                f'&mqtt_host={qrkey_settings.mqtt_host}'
                f'&mqtt_port={qrkey_settings.mqtt_ws_port}'
                f'&mqtt_version={qrkey_settings.mqtt_version}'
                '&mqtt_use_ssl=True'
            ),
            id='SSLSet',
        ),
    ],
)
async def test_get_qr_code(version, use_ssl, username, password, url):
    buff = io.BytesIO()
    qrkey_settings.mqtt_version = version
    qrkey_settings.mqtt_use_ssl = use_ssl
    qrkey_settings.mqtt_username = username
    qrkey_settings.mqtt_password = password
    qrcode = segno.make_qr(url)
    qrcode.save(buff, kind='svg', scale=10, light=None)
    response = await client.get('/pin_code/qr_code')
    assert response.status_code == 200
    assert response.content == buff.getvalue()


@pytest.mark.asyncio
async def test_ws_client():
    with TestClient(api).websocket_connect('/ws') as websocket:
        await asyncio.sleep(0.1)
        assert len(api.controller.websockets) == 1
        websocket.close()
        await asyncio.sleep(0.1)
        assert len(api.controller.websockets) == 0


def test_import_succeeds_without_ui_bundle(tmp_path):
    # Regression check: `import qrkey.api` must succeed on a fresh clone
    # that has not built the React UI bundle. Copies the qrkey package
    # to a tempdir minus qrkey/ui/build/ and imports it in a subprocess
    # so this test never affects the rest of the suite.
    import shutil

    src_pkg = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    dest_pkg = tmp_path / 'qrkey'
    shutil.copytree(src_pkg, dest_pkg)
    shutil.rmtree(dest_pkg / 'ui' / 'build', ignore_errors=True)
    assert not (dest_pkg / 'ui' / 'build').exists()

    # The /pin path is used ONLY by the StaticFiles mount; route name
    # 'pin_code' is shared with the @api.get('/pin_code') endpoint, so
    # we discriminate by path here.
    result = subprocess.run(
        [
            sys.executable,
            '-c',
            'import sys; sys.path.insert(0, %r); '
            'import qrkey.api as m; '
            'import os.path; '
            "assert not os.path.isdir(m.PIN_CODE_DIR), 'UI dir should be absent'; "
            "assert all(getattr(r, 'path', None) != '/pin' for r in m.api.routes), "
            "'StaticFiles /pin mount should be skipped'; "
            "print('ok')" % str(tmp_path),
        ],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, (
        f'import failed:\nstdout={result.stdout}\nstderr={result.stderr}'
    )
    assert result.stdout.strip() == 'ok'
