"""Module for settings."""

# SPDX-FileCopyrightText: 2024-present Alexandre Abadie <alexandre.abadie@inria.fr>
#
# SPDX-License-Identifier: BSD-3-Clause

from typing import Optional

from gmqtt.mqtt.constants import MQTTv50  # type: ignore
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class QrkeySettings(BaseSettings):
    """Mqtt broker connection settings."""

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8')
    frontend_base_url: str = Field(default='http://localhost:8080')
    mqtt_host: str = Field(default='localhost')
    mqtt_port: int = Field(default=1883)
    mqtt_use_ssl: bool = Field(default=False)
    mqtt_username: Optional[str] = Field(default=None)
    mqtt_password: Optional[str] = Field(default=None)

    mqtt_version: Optional[int] = Field(default=MQTTv50)
    mqtt_keepalive: Optional[int] = Field(default=60)
    mqtt_reconnect_retries: Optional[int] = Field(default=3)
    mqtt_reconnect_delay: Optional[int] = Field(default=5)


qrkey_settings = QrkeySettings()
