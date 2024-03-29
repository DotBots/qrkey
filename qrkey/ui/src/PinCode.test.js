import { http, HttpResponse } from 'msw'
import { setupServer } from 'msw/node'
import WS from 'jest-websocket-mock';

import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { PinCode } from './PinCode';

const TestPinCode = 12345678;

const handlers = [
  http.get('/pin_code', () => {
    return HttpResponse.json({"pin": TestPinCode});
  }),
  http.get('/pin_code/qr_code', () => {
    return HttpResponse.xml("<svg></svg>");
  }),
];

const writeText = jest.fn()

Object.assign(navigator, {
  clipboard: {
    writeText,
  },
});

const server = setupServer(...handlers);

const wsServer = new WS("ws://localhost:8080/ws");
const waitForElementOptions = {timeout: 2000};

beforeAll(() => {
  server.listen();
  navigator.clipboard.writeText.mockResolvedValue(undefined);
});
afterEach(() => { server.resetHandlers(); });
afterAll(() => { server.close(); });

test('Renders Pin Code', async () => {
  const logSpy = jest.spyOn(console, 'log');
  render(<PinCode />)
  await screen.findByRole("PinCode", {waitForElementOptions: waitForElementOptions});

  // Checking PinCode is absent
  const pinCode = screen.queryByText(/Pin Code/)
  expect(pinCode).toBeNull()

  // Checking QrCode is absent
  const qrCode = screen.queryByRole("QrCode")
  expect(qrCode).toBeNull()

  // Once loaded and fetched, PinCode should be here
  await screen.findByText(/Pin Code/, {waitForElementOptions: waitForElementOptions});
  screen.getByText(`${TestPinCode}`);

  // Checking QrCode is also here
  await screen.findByRole("QrCode", {waitForElementOptions: waitForElementOptions});

  // Testing websocket
  expect(logSpy).toHaveBeenCalledWith('websocket opened');
  wsServer.send(JSON.stringify({cmd: 2})); // cmd != 255 should be ignored
  screen.getByText(`${TestPinCode}`);

  wsServer.send(JSON.stringify({cmd: 255, pin_code: "87654321"}));
  await screen.findByText("87654321", {waitForElementOptions: waitForElementOptions});
  wsServer.close();
  expect(logSpy).toHaveBeenCalledWith('websocket closed');

  // Checking QrCode is also here
  const button = screen.queryByRole("button")
  fireEvent.click(button);
  await waitFor(() => {
    expect(navigator.clipboard.writeText).toHaveBeenCalledWith("87654321");
  });
});
