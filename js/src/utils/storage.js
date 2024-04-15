import logger from './logger';
const log = logger.child({module: 'storage'});

export const loadLocalPin = () => {
  const pin = parseInt(localStorage.getItem("pin"));
  const date = parseInt(localStorage.getItem("date"));

  if (isNaN(pin) || isNaN(date)) {
    log.debug("No pin found in local storage");
    return null;
  }

  if (Date.now() - date > 1000 * 60 * 20) {
    log.debug("Pin found in local storage, but it's too old");
    return null;
  }

  log.debug(`Pin ${pin} found in local storage`);

  return pin;
};

export const saveLocalPin = (pin) => {
  log.debug(`Saving pin ${pin} to local storage`);
  localStorage.setItem("pin", pin);
  localStorage.setItem("date", Date.now());
};
