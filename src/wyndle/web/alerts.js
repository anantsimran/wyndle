// Shared delivery and scheduling for the dashboard and Daily Alarm page.
const preferences = { timer: 'wyndle.focusAlerts', daily: 'wyndle-daily-alerts' };
const read = key => { try { return localStorage.getItem(key); } catch { return null; } };
const write = (key, value) => { try { localStorage.setItem(key, value); } catch { /* memory works */ } };
const enabled = channel => read(preferences[channel]) === (channel === 'timer' ? 'on' : 'true');
let host = false;
let hostOrigin;
let registration;
let deliveryError = '';
const embedded = window.parent !== window;
const needsHomeScreen = (/iPhone|iPad|iPod/.test(navigator.userAgent)
  || (/Macintosh/.test(navigator.userAgent) && navigator.maxTouchPoints > 1))
  && !navigator.standalone && !matchMedia('(display-mode: standalone)').matches;
if (embedded) window.parent.postMessage({ type: 'wyndle.host.request' }, '*');
const hostMessage = event => embedded && event.source === window.parent
  && (/^vscode-webview:\/\/[a-z0-9-]+$/i.test(event.origin)
    || /^https:\/\/[a-z0-9-]+\.vscode-cdn\.net$/i.test(event.origin))
  && event.data?.type === 'wyndle.host.ready';
window.addEventListener('message', event => {
  if (hostMessage(event)) { host = true; hostOrigin = event.origin; }
});

async function worker() {
  if (!window.isSecureContext || !('serviceWorker' in navigator) || embedded) return null;
  if (!registration) registration = (async () => {
    await navigator.serviceWorker.register('/notification-worker.js');
    let timeout;
    try {
      return await Promise.race([navigator.serviceWorker.ready,
        new Promise((_, reject) => { timeout = setTimeout(() => reject(new Error('Notification setup timed out.')), 10000); })]);
    } finally { clearTimeout(timeout); }
  })().catch(error => { registration = undefined; throw error; });
  return registration;
}

function status() {
  if (host) return 'VS Code notifications are on while Wyndle is connected.';
  if (embedded) return 'In-page reminders only. Open Wyndle in your browser for notification permission.';
  if (!window.isSecureContext) return 'In-page reminders only. Open the private HTTPS address to enable banners.';
  if (needsHomeScreen) return 'In-page reminders only. Use Share → Add to Home Screen, open Wyndle from that icon, then enable notifications.';
  if (!('Notification' in window)) return 'In-page reminders only. On iPhone or iPad, add Wyndle to your Home Screen and open it there to allow notifications.';
  if (Notification.permission === 'denied') return 'In-page reminders only. Allow notifications in this site’s browser settings, then test again.';
  if (Notification.permission !== 'granted') return 'In-page reminders only. Use Test alert and allow notifications when prompted.';
  if (deliveryError) return `In-page reminders only. ${deliveryError}`;
  return 'Browser notifications are allowed. Use Test alert to check delivery; keep Wyndle open.';
}

async function permission() {
  deliveryError = '';
  if (host || embedded || needsHomeScreen || !('Notification' in window)) return;
  if (Notification.permission === 'default') {
    try { await Notification.requestPermission(); }
    catch { deliveryError = 'The browser could not request notification permission.'; }
  }
}

async function banner(event) {
  if (host) {
    window.parent.postMessage({ type: 'wyndle.alert', event }, hostOrigin);
    return true;
  }
  if (!('Notification' in window) || Notification.permission !== 'granted') return false;
  const options = { body: event.body, tag: `wyndle-${event.channel}`, silent: true,
    icon: '/favicon.png', data: { url: event.url || '/' } };
  try {
    let serviceWorker;
    try { serviceWorker = await worker(); } catch { /* Desktop constructor can still work. */ }
    if (serviceWorker) await serviceWorker.showNotification(`Wyndle · ${event.title}`, options);
    else new Notification(`Wyndle · ${event.title}`, options);
    deliveryError = '';
    return true;
  } catch {
    deliveryError = 'The browser could not show a banner. Check notification settings and try Test alert again.';
    return false;
  }
}

export function createAlerts({ channel, toast }) {
  const $ = id => document.getElementById(id);
  const button = $(channel === 'timer' ? 'focus-alerts' : 'enable-alerts');
  const statusNode = $(channel === 'timer' ? 'focus-alert-status' : 'alert-status');
  const testButton = $(channel === 'timer' ? 'focus-alert-test' : 'daily-alert-test');
  const on = { timer: enabled('timer'), daily: enabled('daily') };
  const seen = {};
  const identities = {};
  const pending = new Map();
  const delivered = new Set();
  let state;
  let receivedAt;
  let testing = false;
  const now = () => state.now + (Date.now() - receivedAt) / 1000;
  function render() {
    button.textContent = `${on[channel] ? 'Disable' : 'Enable'} ${channel === 'timer' ? 'timer' : 'page'} alerts`;
    button.setAttribute('aria-pressed', String(on[channel]));
    statusNode.textContent = on[channel] ? status() : 'Alerts are off on this device.';
  }
  function syncHost() {
    if (host) window.parent.postMessage({ type: 'wyndle.alertPreferences', enabled: on }, hostOrigin);
  }
  async function send(event) {
    const key = `wyndle.lastAlert.${event.channel}`;
    if (delivered.has(event.id) || read(key) === event.id) return;
    delivered.add(event.id);
    const shown = await banner(event);
    if (!document.hidden) toast(`${event.title}. ${event.body}`);
    else if (!shown) {
      pending.set(event.channel, event);
      delivered.delete(event.id);
      render();
      return; // A visible tab can still deliver this event.
    }
    write(key, event.id);
    render();
  }
  function tick() {
    if (!state) return;
    const time = now();
    for (const kind of Object.keys(on)) {
      const crossed = (state.reminders || []).filter(event => event.channel === kind
        && seen[kind] < event.at && event.at <= time).sort((a, b) => a.at - b.at);
      seen[kind] = time;
      if (on[kind] && crossed.length) {
        const event = crossed.at(-1);
        // Web Locks serialize claims across open tabs where supported.
        if (navigator.locks) navigator.locks.request(`wyndle-alert-${kind}`, () => send(event));
        else send(event);
      }
    }
  }
  button.addEventListener('click', async () => {
    on[channel] = !on[channel];
    write(preferences[channel], channel === 'timer' ? (on[channel] ? 'on' : 'off') : String(on[channel]));
    if (state) seen[channel] = now();
    if (!on[channel]) pending.delete(channel);
    render();
    syncHost();
    if (on[channel]) { await permission(); render(); }
  });
  testButton.addEventListener('click', async () => {
    if (testing) return;
    testing = true;
    testButton.disabled = true;
    try {
      await permission();
      const shown = await banner({ id: `test:${Date.now()}`, channel, title: 'Test alert',
        body: 'Notifications are working on this device.', url: channel === 'timer' ? '/' : '/daily' });
      toast(shown ? 'Test alert submitted. If no banner appears, check system notifications and Focus / Do Not Disturb.' : status());
      render();
    } finally { testing = false; testButton.disabled = false; }
  });
  window.addEventListener('storage', event => {
    for (const kind of Object.keys(on)) if (event.key === preferences[kind]) on[kind] = enabled(kind);
    render(); syncHost();
  });
  window.addEventListener('message', event => {
    if (hostMessage(event)) { render(); syncHost(); }
  });
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
      for (const [kind, event] of pending) if (on[kind] && read(`wyndle.lastAlert.${kind}`) !== event.id) {
        toast(`${event.title}. ${event.body}`);
        write(`wyndle.lastAlert.${kind}`, event.id);
        delivered.add(event.id);
      }
      pending.clear(); render(); tick();
    }
  });
  render();
  setInterval(tick, 1000);
  return { update(value) {
    if (state === value) return; // A busy-state render must not rewind the clock.
    state = value; receivedAt = Date.now();
    for (const kind of Object.keys(on)) {
      const identity = kind === 'timer' ? `${state.date}:${state.timer.kind}:${state.timer.end}` : state.dailyAlarm?.id;
      if (identities[kind] !== identity || seen[kind] === undefined) seen[kind] = now();
      identities[kind] = identity;
    }
    tick();
  } };
}
