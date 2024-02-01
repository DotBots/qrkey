# SPDX-FileCopyrightText: 2024-present Alexandre Abadie <alexandre.abadie@inria.fr>
#
# SPDX-License-Identifier: BSD-3-Clause

from unittest.mock import MagicMock

import pytest  # type: ignore
from httpx import AsyncClient

from qrkey.api import api
from qrkey.models import (
    MqttPinCodeModel,
)

client = AsyncClient(app=api, base_url='http://testserver')


@pytest.fixture(autouse=True)
def controller():
    api.controller = MagicMock()
    api.controller.pin_code = '12345678'
    api.controller.websockets = []


@pytest.mark.asyncio
async def test_openapi_exists():
    response = await client.get('/api')
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_pin_code():
    # api.controller.pin_code.return_value = "12345678"
    response = await client.get('/pin_code')
    assert response.status_code == 200
    assert response.json() == MqttPinCodeModel(pin='12345678').model_dump()
