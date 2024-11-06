import { useCallback, useEffect, useState } from "react"; 
import { useMqttBroker } from "./mqtt";
import { deriveKey, deriveTopic } from "../utils/crypto";
import { loadLocalMqttData, saveLocalMqttData } from "../utils/storage";

import logger from '../utils/logger';
const log = logger.child({module: 'qrkey'});

const NotificationType = {
  PinCodeUpdate: 255,
};

export const useQrKey = ({ rootTopic, setQrKeyMessage, searchParams, setSearchParams }) => {
  const [initializing, setInitializing] = useState(true);
  const [ready, setReady] = useState(false);
  const [previousPin, setPreviousPin] = useState(null);
  const [mqttData, setMqttData] = useState(null);
  const [mqttSubscribed, setMqttSubscribed] = useState(false);
  const [request, setRequest] = useState(null);
  const [message, setMessage] = useState(null);
  const [clientId, setClientId] = useState(null);

  const pin = mqttData ? mqttData.pin : null;
  const use_ssl = mqttData ? mqttData.mqtt_use_ssl : false;
  const mqtt_host = mqttData ? mqttData.mqtt_host : null;
  const mqtt_port = mqttData ? mqttData.mqtt_port : null;
  const mqtt_version = mqttData ? mqttData.mqtt_version : null;
  const mqtt_username = mqttData ? mqttData.mqtt_username : null;
  const mqtt_password = mqttData ? mqttData.mqtt_password : null;

  const secretKey = deriveKey(pin);
  const secretTopic = deriveTopic(pin);
  const previousSecretTopic = deriveTopic(previousPin);

  const [client, connected, mqttPublish, mqttSubscribe, mqttUnsubscribe] = useMqttBroker({
    start: pin !== null,
    brokerUrl: `ws${use_ssl ? "s": ""}://${mqtt_host}:${mqtt_port}/mqtt`,
    brokerOptions: {
      keepalive: 60,
      clean: true,
      reconnectPeriod: 1000,
      connectTimeout: 10 * 1000,
      protocolVersion: mqtt_version,
      username: mqtt_username,
      password: mqtt_password,
    },
    setMessage: setMessage,
    secretKey: secretKey,
  });

  const handleMessage = useCallback(() => {
    log.debug(`Handle received message: ${JSON.stringify(message)}`);
    let parsed = null;
    try {
      parsed = JSON.parse(message.payload);
    } catch (error) {
      log.warn(`${error.name}: ${error.message}`);
      return;
    }
    if ((parsed.timestamp < (Date.now() / 1000) - 30) || (parsed.timestamp > (Date.now() / 1000) + 30)) {
      log.warn(`Message timestamp out of range: ${parsed.timestamp}`);
      return;
    }
    if (message.topic === `${rootTopic}/${secretTopic}/notify` && parsed.cmd === NotificationType.PinCodeUpdate) {
      const mqttDataTmp = { ...mqttData };
      mqttDataTmp.pin = parsed.pin_code;
      saveLocalMqttData(mqttDataTmp);
      setMqttData(mqttDataTmp);
    } else {
      let qrkeyMessage = {topic: message.topic.replace(`${rootTopic}/${secretTopic}`, ""), payload: parsed.payload};
      setQrKeyMessage(qrkeyMessage);
    }
    setMessage(null);
  }, [message, setMessage, setQrKeyMessage, saveLocalMqttData, setMqttData, secretTopic]
  );

  const publish = useCallback(async (subTopic, payload) => {
    const baseTopic = `${rootTopic}/${secretTopic}`;
    const message = {
      timestamp: Date.now() / 1000,  // in seconds
      payload: payload,
    }
    await mqttPublish(`${baseTopic}/${subTopic}`, JSON.stringify(message));
  }, [mqttPublish, secretTopic]
  );

  const publishCommand = async (address, application, command_topic, command) => {
    const subTopic = `command/0000/${address}/${application}/${command_topic}`;
    await publish(subTopic, command);
  }

  const publishRequest = useCallback(async () => {
    await publish("request", request);
    setRequest(null);
  }, [request, publish]
  );

  const sendRequest = useCallback((request) => {
    setRequest(request);
  }, [setRequest]
  );

  const setupSubscriptions = useCallback((topic) => {
    if (mqttSubscribed) {
      return;
    }
    [
      `${rootTopic}/${topic}/notify`,
      `${rootTopic}/${topic}/reply/${client.options.clientId}`,
    ].forEach((t) => {mqttSubscribe(t)});
    setMqttSubscribed(true);
  }, [mqttSubscribed, setMqttSubscribed, mqttSubscribe, client]
  );

  const disableSubscriptions = useCallback((topic) => {
    [
      `${rootTopic}/${topic}/notify`,
      `${rootTopic}/${topic}/reply/${client.options.clientId}`,
    ].forEach((t) => {mqttUnsubscribe(t)});
    setMqttSubscribed(false);
  }, [setMqttSubscribed, mqttUnsubscribe, client]
  );

  useEffect(() => {
    if (mqttData) {
      return;
    }

    if (!mqttData &&
      searchParams &&
      searchParams.has('pin') &&
      searchParams.has('mqtt_host') && searchParams.has('mqtt_port') &&
      searchParams.has('mqtt_version') && searchParams.has('mqtt_use_ssl')
    ) {
      console.log("Loading from query string");
      const queryMqttData = {
        pin: searchParams.get('pin'),
        mqtt_host: searchParams.get('mqtt_host'),
        mqtt_port: searchParams.get('mqtt_port'),
        mqtt_version: searchParams.get('mqtt_version'),
        mqtt_use_ssl: searchParams.get('mqtt_use_ssl') === "True",
      };
      log.debug(`Pin ${queryMqttData.pin} provided in query string`);
      saveLocalMqttData(queryMqttData);
      searchParams.delete('pin');
      searchParams.delete('mqtt_host');
      searchParams.delete('mqtt_port');
      searchParams.delete('mqtt_version');
      searchParams.delete('mqtt_use_ssl');
      searchParams.delete('mqtt_username');
      searchParams.delete('mqtt_password');
      setSearchParams(searchParams);
      return;
    }

    if (!mqttData) {
      log.debug("Loading from local storage");
      const localMqttData = loadLocalMqttData();
      setMqttData(localMqttData);
    }

    setInitializing(false);

  }, [mqttData, setMqttData, searchParams, setSearchParams, setInitializing]
  );

  useEffect(() => {
    if (!mqttData) {
      return;
    }

    if (previousPin !== mqttData.pin) {
        saveLocalMqttData(mqttData);
    }

    if (connected) {
      if (mqttSubscribed && previousPin !== mqttData.pin) {
        disableSubscriptions(previousSecretTopic);
      }

      if (!mqttSubscribed) {
        setupSubscriptions(secretTopic);
        setPreviousPin(mqttData.pin);
      }
    }
  }, [
    mqttData, previousPin, setPreviousPin,
    connected, mqttSubscribed,
    disableSubscriptions, setupSubscriptions,
    secretTopic, previousSecretTopic,
  ]);

  useEffect(() => {
    if (!connected) {
      return;
    }

    if (clientId && client.options.clientId === clientId) {
      return;
    }

    setClientId(client.options.clientId);
  }, [connected, clientId, setClientId, client]
  );

  useEffect(() => {
    setReady(!initializing);
  }, [setReady, initializing]
  );

  useEffect(() => {
    // Publish the request if connected and a request is pending
    if (!connected || !request) {
      return;
    }

    publishRequest();
  }, [connected, request, publishRequest]
  );

  useEffect(() => {
    // Process incoming messages if any
    if (!message) {
      return;
    }

    handleMessage(message.topic, message.payload);
  }, [message, handleMessage]
  );

  return [ready, clientId, mqttData, setMqttData, publish, publishCommand, sendRequest];
};
