"""Module for MQTT communication."""

# SPDX-FileCopyrightText: 2024-present Alexandre Abadie <alexandre.abadie@inria.fr>
#
# SPDX-License-Identifier: BSD-3-Clause

import asyncio
import json
import re
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

import structlog
import uvicorn
import websockets

from fastapi import WebSocket
from gmqtt import Client as MQTTClient  # type: ignore
from pydantic import ValidationError

from qrkey.api import api
from qrkey.crypto import (
    decrypt,
    derive_aes_key,
    derive_topic,
    encrypt,
    generate_pin_code,
)
from qrkey.models import (
    NotificationModel,
    NotificationType,
    PayloadModel,
    SubscriptionModel,
)
from qrkey.settings import qrkey_settings


class QrkeyController:
    def __init__(
        self,
        request_callback: Callable,
        logger: structlog.stdlib.BoundLogger,
        root_topic: str = '/qrkey',
    ):
        self.logger = logger.bind(context=__name__)
        self.root_topic = root_topic
        self.client: MQTTClient = MQTTClient(f'qrkey-{uuid.uuid4().hex}')
        self.client.set_config(qrkey_settings.model_dump(exclude_none=True))
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.client.on_subscribe = self.on_subscribe
        self.websockets: List[WebSocket] = []
        api.controller = self
        self.message_callback_map: Dict[str, Callable] = {}
        self.request_callback: Callable = request_callback
        self.pin_code: str = generate_pin_code()
        self.mqtt_aes_key: bytes = derive_aes_key(self.pin_code)
        self.mqtt_topic: str = derive_topic(self.pin_code)
        self.old_mqtt_aes_key = self.mqtt_aes_key
        self.old_mqtt_topic = self.mqtt_topic

    @property
    def base_topic(self):
        return f'{self.root_topic}/{self.mqtt_topic}'

    @property
    def old_base_topic(self):
        if self.old_mqtt_topic is None:
            return None
        return f'{self.root_topic}/{self.old_mqtt_topic}'

    def on_connect(self, _, flags, rc, properties):
        logger = self.logger.bind(
            context=__name__,
            rc=rc,
            flags=flags,
            **properties,
            **qrkey_settings.model_dump(exclude='frontend_base_url', exclude_none=True),
        )
        logger.info('Connected to broker')

    def on_message(self, _, topic, payload, qos, properties):
        logger = self.logger.bind(topic=topic, qos=qos, **properties)
        sub_topic = topic.replace(self.base_topic, '')
        decrypt_key = self.mqtt_aes_key
        if topic.startswith(self.old_base_topic) and self.old_mqtt_aes_key is not None:
            sub_topic = topic.replace(self.old_base_topic, '')
            decrypt_key = self.old_mqtt_aes_key
        payload = decrypt(payload, decrypt_key)
        if not payload:
            logger.warning('Cannot decrypt received payload')
            return
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            logger.warning('Cannot parse payload as JSON')
            return
        try:
            payload = PayloadModel(**payload)
        except ValidationError as exc:
            logger.warning(f'Invalid payload received: {exc.errors()}')
            return
        if payload.timestamp < time.time() - 1 or payload.timestamp > time.time() + 1:
            logger.warning(
                f'Invalid payload timestamp {payload.timestamp}, {time.time()}'
            )
            return
        payload = payload.payload
        if sub_topic == '/request':
            self.request_callback(payload)
        else:
            for registered_topic in self.message_callback_map.keys():
                topic_regex = (
                    r'^'
                    + r'\/'.join(registered_topic.split('/')).replace('+', '.+')
                    + r'$'
                )
                if re.match(topic_regex, sub_topic):
                    self.message_callback_map[registered_topic](sub_topic, payload)
                    break

    def on_disconnect(self, _, packet, exc=None):
        logger = self.logger.bind(packet=packet, exc=exc)
        logger.info('Disconnected')

    def on_subscribe(self, client, mid, qos, properties):
        logger = self.logger.bind(qos=qos, **properties)
        topic = (
            client.get_subscriptions_by_mid(mid)[0].topic
            if client.get_subscriptions_by_mid(mid)
            else None
        )
        logger.info(f'Subscribed to {topic}')

    def _update_crypto(self):
        self.old_mqtt_aes_key = self.mqtt_aes_key
        self.old_mqtt_topic = self.mqtt_topic
        self.mqtt_aes_key = derive_aes_key(self.pin_code)
        self.mqtt_topic = derive_topic(self.pin_code)
        self.logger.debug(
            'MQTT crypto update',
            pin_code=self.pin_code,
            aes_key=self.mqtt_aes_key.hex(),
            topic=self.mqtt_topic,
        )

    def _setup_default_subscriptions(self):
        if self.client.is_connected is not True:
            return
        self.client.subscribe(f'{self.base_topic}/request')

    def _setup_user_subscriptions(self):
        if self.client.is_connected is not True:
            return
        for topic in self.message_callback_map.keys():
            self.client.subscribe(f'{self.base_topic}{topic}')

    async def _disable_old_mqtt_crypto(self):
        """Disable old MQTT crypto after 5 minutes."""
        if self.client.is_connected is not True:
            return
        await asyncio.sleep(qrkey_settings.pin_code_revoke_delay)
        self.logger.info('Last pin code update notification', topic=self.old_base_topic)
        # Send the pin code update notification on the old topic with the old key
        notification = NotificationModel(
            cmd=NotificationType.PIN_CODE_UPDATE,
            pin_code=self.pin_code,
        )
        message = encrypt(
            json.dumps(notification.model_dump(exclude_none=True)),
            self.old_mqtt_aes_key,
        )
        self.client.publish(f'{self.old_base_topic}/notify', message)
        self.logger.info('Disabling old MQTT crypto')
        for subscription in self.client.subscriptions:
            if subscription.topic.startswith(self.old_base_topic):
                self.logger.info(f'Unsubscribe from {subscription.topic}')
                self.client.unsubscribe(subscription.topic)
        self.old_mqtt_aes_key = None
        self.old_mqtt_topic = None

    async def _ws_send_safe(self, websocket: WebSocket, msg: str):
        """Safely send a message to a websocket client."""
        try:
            await websocket.send_text(msg)
        except websockets.exceptions.ConnectionClosedError:
            await asyncio.sleep(0.1)

    async def _notify_pin_code_update(self, notification: NotificationModel):
        """Send a pin code update to all web clients connected."""
        self.logger.debug('notify', cmd=notification.cmd.name)
        await asyncio.gather(*[
            self._ws_send_safe(
                websocket, json.dumps(notification.model_dump(exclude_none=True))
            )
            for websocket in self.websockets
        ])

    async def _rotate_pin_code(self):
        while 1:
            await asyncio.sleep(qrkey_settings.pin_code_refresh_interval)
            self.pin_code = generate_pin_code()
            self._update_crypto()
            self._setup_default_subscriptions()
            self._setup_user_subscriptions()
            # Send the pin code update notification on the old topic with the old key
            notification = NotificationModel(
                cmd=NotificationType.PIN_CODE_UPDATE,
                pin_code=self.pin_code,
            )
            message = encrypt(
                json.dumps(notification.model_dump(exclude_none=True)),
                self.old_mqtt_aes_key,
            )
            self.client.publish(f'{self.old_base_topic}/notify', message)
            await self._notify_pin_code_update(notification)
            asyncio.create_task(self._disable_old_mqtt_crypto())

    async def api(self):
        """Starts the web server application."""
        config = uvicorn.Config(api, port=8080, log_level='critical')
        server = uvicorn.Server(config)

        try:
            self.logger.info('Starting qrkey web server')
            await server.serve()
        except asyncio.exceptions.CancelledError:
            self.logger.info('Qrkey web server cancelled')
        else:
            self.logger.info('Stopping qrkey web server')
            raise SystemExit

    async def start(self, subscriptions: Optional[List[SubscriptionModel]] = None):
        self.logger.info('Starting qrkey controller')
        await self.client.connect(
            host=qrkey_settings.mqtt_host,
            port=qrkey_settings.mqtt_port,
            ssl=qrkey_settings.mqtt_use_ssl,
            keepalive=qrkey_settings.mqtt_keepalive,
            version=qrkey_settings.mqtt_version,
        )
        self._setup_default_subscriptions()
        if subscriptions is not None:
            for subscription in subscriptions:
                self.subscribe(subscription.topic, subscription.callback)
        tasks = []
        try:
            tasks = [
                asyncio.create_task(self.api()),
                asyncio.create_task(self._rotate_pin_code()),
            ]
            await asyncio.gather(*tasks)
        except SystemExit:
            self.logger.info('Stopping qrkey controller')
        finally:
            for task in tasks:
                task.cancel()

    def subscribe(self, topic: str, callback: Callable):
        if topic == '/request':
            self.logger.warning('Cannot subscribe to /request topic')
            return
        full_topic = f'{self.base_topic}{topic}'
        self.client.subscribe(full_topic)
        self.message_callback_map.update({topic: callback})

    def publish(self, topic: str, message: Any):
        payload = PayloadModel(timestamp=time.time(), payload=message)
        self.client.publish(
            f'{self.base_topic}{topic}',
            encrypt(json.dumps(payload.model_dump()), self.mqtt_aes_key),
        )
        if (
            self.old_mqtt_aes_key is not None
            and self.old_mqtt_aes_key != self.mqtt_aes_key
        ):
            self.client.publish(
                f'{self.old_base_topic}{topic}',
                encrypt(json.dumps(payload.model_dump()), self.old_mqtt_aes_key),
            )
