# SPDX-FileCopyrightText: 2024-present Alexandre Abadie <alexandre.abadie@inria.fr>
#
# SPDX-License-Identifier: BSD-3-Clause

import asyncio
import io
from unittest.mock import MagicMock

import pytest  # type: ignore
import segno

from fastapi.testclient import TestClient
from httpx import AsyncClient

from qrkey.api import api
from qrkey.models import (
    MqttPinCodeModel,
)
from qrkey.settings import qrkey_settings


client = AsyncClient(app=api, base_url='http://testserver')

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
async def test_get_qr_code():
    buff = io.BytesIO()
    qrcode = segno.make_qr(f'{qrkey_settings.frontend_base_url}?pin={TEST_PIN_CODE}')
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
