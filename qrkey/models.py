"""Pydantic models used by the controller and server application."""

# SPDX-FileCopyrightText: 2024-present Alexandre Abadie <alexandre.abadie@inria.fr>
#
# SPDX-License-Identifier: BSD-3-Clause

from enum import IntEnum
from typing import Any, Callable, Optional

from pydantic import BaseModel


class MqttPinCodeModel(BaseModel):
    """Pin code used to derive crypto keys for MQTT."""

    pin: int


class NotificationType(IntEnum):
    """Notification types for qrkey."""

    PIN_CODE_UPDATE: int = 255


class NotificationModel(BaseModel):
    """Model class used to send controller notifications."""

    cmd: NotificationType
    pin_code: Optional[str] = None


class PayloadModel(BaseModel):
    """Model class used to send/received payload over MQTT."""

    timestamp: float
    payload: Any


class SubscriptionModel(BaseModel):
    """Model class used to subscribe to MQTT topics."""

    topic: str
    callback: Callable
