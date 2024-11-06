"""Module for the web server application."""

# SPDX-FileCopyrightText: 2024-present Alexandre Abadie <alexandre.abadie@inria.fr>
#
# SPDX-License-Identifier: BSD-3-Clause

import io
import os

import segno
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles

from qrkey.__about__ import __version__
from qrkey.models import (
    MqttPinCodeModel,
)
from qrkey.settings import qrkey_settings


api = FastAPI(
    debug=False,
    title='Qrkey controller API',
    description='This is the Qrkey controller API',
    version=__version__,
    docs_url='/api',
    redoc_url=None,
)
api.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@api.get(
    path='/pin_code',
    response_model=MqttPinCodeModel,
    summary='Return the current pin code',
    tags=['mqtt'],
)
async def pin_code():
    """Returns the pin code."""
    return MqttPinCodeModel(
        pin=api.controller.pin_code,
    )


@api.get(
    path='/pin_code/qr_code',
    response_class=Response,
    summary='Return the current QR code',
    tags=['mqtt'],
)
async def pin_code_qr_code():
    """Returns the MQTT data encoded in a QR code."""
    buff = io.BytesIO()
    url = (
        f'{qrkey_settings.frontend_base_url}?'
        f'pin={api.controller.pin_code!s}&'
        f'mqtt_host={qrkey_settings.mqtt_host!s}&'
        f'mqtt_port={qrkey_settings.mqtt_ws_port!s}&'
        f'mqtt_version={qrkey_settings.mqtt_version!s}&'
        f'mqtt_use_ssl={qrkey_settings.mqtt_use_ssl!s}'
    )
    if qrkey_settings.mqtt_username is not None:
        url += f'&mqtt_username={qrkey_settings.mqtt_username!s}'
    if qrkey_settings.mqtt_password is not None:
        url += f'&mqtt_password={qrkey_settings.mqtt_password!s}'
    qrcode = segno.make_qr(url)
    qrcode.save(buff, kind='svg', scale=10, light=None)
    headers = {'Cache-Control': 'no-cache'}
    return Response(
        buff.getvalue().decode(),
        headers=headers,
        media_type='image/svg+xml',
    )


@api.websocket('/ws')
async def websocket_endpoint(websocket: WebSocket):
    """Websocket server endpoint."""
    await websocket.accept()
    api.controller.websockets.append(websocket)
    try:
        while True:
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in api.controller.websockets:
            api.controller.websockets.remove(websocket)


# Mount static files after all routes are defined
PIN_CODE_DIR = os.path.join(os.path.dirname(__file__), 'ui', 'build')
api.mount('/pin', StaticFiles(directory=PIN_CODE_DIR, html=True), name='pin_code')
