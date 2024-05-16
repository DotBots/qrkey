import { useCallback, useEffect, useState } from "react"; 
import { useMqttBroker } from "./mqtt";
import { deriveKey, deriveTopic } from "../utils/crypto";
import { loadLocalPin, saveLocalPin } from "../utils/storage";

import logger from '../utils/logger';
const log = logger.child({module: 'qrkey'});

const NotificationType = {
  PinCodeUpdate: 255,
};

export const useQrKey = ({ brokerHost, brokerPort, brokerUsername, brokerPassword, rootTopic, setQrKeyMessage, searchParams, setSearchParams }) => {
  const [initializing, setInitializing] = useState(true);
  const [ready, setReady] = useState(false);
  const [previousPin, setPreviousPin] = useState(null);
  const [pin, setPin] = useState(null);
  const [mqttSubscribed, setMqttSubscribed] = useState(false);
  const [request, setRequest] = useState(null);
  const [message, setMessage] = useState(null);
  const [clientId, setClientId] = useState(null);

  const secretKey = deriveKey(pin);
  const secretTopic = deriveTopic(pin);
  const previousSecretTopic = deriveTopic(previousPin);

  const [client, connected, mqttPublish, mqttSubscribe, mqttUnsubscribe] = useMqttBroker({
    start: pin !== null,
    brokerUrl: `wss://${brokerHost}:${brokerPort}`,
    brokerOptions: {
      keepalive: 60,
      clean: true,
      reconnectPeriod: 1000,
      connectTimeout: 10 * 1000,
      protocolVersion: 5,
      username: brokerUsername,
      password: brokerPassword,
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
    if ((parsed.timestamp < (Date.now() / 1000) - 5) || (parsed.timestamp > (Date.now() / 1000) + 5)) {
      log.warn(`Message timestamp out of range: ${parsed.timestamp}`);
      return;
    }
    if (message.topic === `${rootTopic}/${secretTopic}/notify` && parsed.cmd === NotificationType.PinCodeUpdate) {
      saveLocalPin(parsed.pin_code);
      setPin(parsed.pin_code);
    } else {
      let qrkeyMessage = {topic: message.topic.replace(`${rootTopic}/${secretTopic}`, ""), payload: parsed.payload};
      setQrKeyMessage(qrkeyMessage);
    }
    setMessage(null);
  }, [message, setMessage, saveLocalPin, setPin, secretTopic]
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
    if (pin) {
      return;
    }

    if (!pin && searchParams && searchParams.has('pin')) {
      const queryPin = searchParams.get('pin');
      log.debug(`Pin ${queryPin} provided in query string`);
      saveLocalPin(queryPin);
      searchParams.delete('pin');
      setSearchParams(searchParams);
      return;
    }

    if (!pin) {
      log.debug("Loading from local storage");
      const localPin = loadLocalPin();
      setPin(localPin);
    }

    setInitializing(false);

  }, [pin, setPin, searchParams, setSearchParams, setInitializing]
  );

  useEffect(() => {
    if (!pin) {
      return;
    }

    if (previousPin !== pin) {
        saveLocalPin(pin);
    }

    if (connected) {
      if (mqttSubscribed && previousPin !== pin) {
        disableSubscriptions(previousSecretTopic);
      }

      if (!mqttSubscribed) {
        setupSubscriptions(secretTopic);
        setPreviousPin(pin);
      }
    }
  }, [
    pin, connected, mqttSubscribed, previousPin,
    disableSubscriptions, previousSecretTopic,
    setupSubscriptions, secretTopic, setPreviousPin,
    request, publishRequest, setRequest
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
  }, [
    connected, request, publishRequest, setRequest
  ]);

  useEffect(() => {
    // Process incoming messages if any
    if (!message) {
      return;
    }

    handleMessage(message.topic, message.payload);
  }, [message, setMessage, handleMessage, mqttSubscribed]
  );

  return [ready, clientId, pin, setPin, publish, publishCommand, sendRequest];
};
