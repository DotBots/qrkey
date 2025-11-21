/* eslint jsx-a11y/aria-role: 0 */

import { useCallback, useState } from "react";
import axios from 'axios';
import useWebSocket from 'react-use-websocket';
import 'bootstrap-icons/font/bootstrap-icons.css';
import './PinCode.css';

let websocketUrl = "ws://localhost:8080/ws";

const PinCodeUpdateValue = 255;

const apiFetchPinCode = async () => {
  console.info(`Fetching Pin Code from ${window.location.origin}/pin_code`);
  return await axios.get(
    `${window.location.origin}/pin_code`,
  ).then(res => res.data);
}

const apiFetchQrCode = async () => {
  console.info(`Fetching QR Code from ${window.location.origin}/pin_code/qr_code`);
  return await axios.get(
    `${window.location.origin}/pin_code/qr_code`,
  ).then(res => res.data);
}

const Animate = ({ children, on, transition }) => {
  return (on === undefined)
    ? <>{children}</>
    : <span className={transition} key={on}>{children}</span>
}

export const PinCode = () => {
  const [ pinCode, setPinCode ] = useState();
  const [ qrCode, setQrCode ] = useState();
  const [ pinCodeCopied, setPinCodeCopied ] = useState(false);

  if (process.env.REACT_APP_WS_URL) {
    websocketUrl = `${window.location.origin.replace(/^https(.*)/, 'wss$1').replace(/^http(.*)/, 'ws$1')}/ws`;
  }

  const fetchPinCode = useCallback(async () => {
    const data = await apiFetchPinCode().catch(error => console.log(error));
    if (data) {
      setPinCode(data.pin);
    }
  }, [setPinCode]
  );

  const fetchQrCode = useCallback(async () => {
    const data = await apiFetchQrCode().catch(error => console.log(error));
    if (data) {
      let parser = new DOMParser();
      let qr_code = parser.parseFromString(data, "image/svg+xml").documentElement.outerHTML;
      setQrCode(qr_code);
    }
  }, [setQrCode]
  );

  const onWsOpen = () => {
    console.log(`websocket opened at ${websocketUrl}`);
    fetchPinCode();
    fetchQrCode();
  };

  const onWsMessage = (event) => {
    const message = JSON.parse(event.data);
    console.log(`websocket message ${message.pin_code}`);
    if (message.cmd === PinCodeUpdateValue) {
      setPinCode(message.pin_code);
      fetchQrCode();
    }
  };

  const onClipboardClick = async () => {
    await navigator.clipboard.writeText(pinCode);
    setPinCodeCopied(true);
    console.log(`Pin Code ${pinCode} copied to clipboard`);
  };

  useWebSocket(websocketUrl, {
    onOpen: () => onWsOpen(),
    onClose: () => console.log("websocket closed"),
    onMessage: (event) => onWsMessage(event),
    shouldReconnect: (event) => true,
  });

  return (
    <div className="PinCode" role="PinCode">
      {qrCode &&
      <Animate on={qrCode} transition="FadeIn">
        <div role="QrCode" className="Pop" dangerouslySetInnerHTML={{ __html: qrCode }} />
      </Animate>
      }
      {pinCode &&
      <p>
        Pin Code: <Animate on={pinCode} transition="FadeIn">{pinCode}</Animate>&nbsp;<button className="Button" type="button" onClick={onClipboardClick}><i className={`bi ${pinCodeCopied ? "bi-clipboard-check": "bi-clipboard"}`}></i></button>
      </p>
      }
    </div>
  );
}
