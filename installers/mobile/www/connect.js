// The first screen of the Android app: pick a Katib server, then open it.
// Everything after that is the server's own web app, so the phone always gets the newest version.

const SERVERS_KEY = 'katib.servers';
const LAST_KEY = 'katib.last';
const MAX_RECENT = 5;

const form = document.getElementById('form');
const input = document.getElementById('address');
const note = document.getElementById('note');
const go = document.getElementById('go');
const label = document.getElementById('label');
const ring = go.querySelector('.ring');
const recent = document.getElementById('recent');
const list = document.getElementById('list');

/** True for addresses that only exist on a private network or this device. */
function isPrivateHost(host) {
  if (host === 'localhost' || host.endsWith('.local')) return true;
  const parts = host.split('.').map(Number);
  if (parts.length !== 4 || parts.some((n) => !Number.isInteger(n) || n < 0 || n > 255)) return false;
  const [a, b] = parts;
  return a === 10 || a === 127 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168) || (a === 169 && b === 254);
}

/** Turn what someone typed into candidate origins to try, safest first. Returns [] when unusable. */
function candidates(text) {
  const typed = text.trim();
  if (!typed || /\s/.test(typed)) return [];
  const withScheme = /^[a-z][a-z0-9+.-]*:\/\//i.test(typed) ? [typed] : [`https://${typed}`, `http://${typed}`];
  const found = [];
  for (const raw of withScheme) {
    try {
      const url = new URL(raw);
      if (url.protocol !== 'https:' && url.protocol !== 'http:') return [];
      if (url.username || url.password) return [];
      found.push(url.origin);
    } catch {
      return [];
    }
  }
  return found;
}

async function reachable(origin) {
  const stop = new AbortController();
  const timer = setTimeout(() => stop.abort(), 6000);
  try {
    // no-cors is enough to learn that something answered. Katib's own page then does the real work.
    await fetch(`${origin}/api/v1/health`, { mode: 'no-cors', cache: 'no-store', signal: stop.signal });
    return true;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

function readRecent() {
  try {
    const data = JSON.parse(localStorage.getItem(SERVERS_KEY) || '[]');
    return Array.isArray(data) ? data.filter((s) => typeof s === 'string').slice(0, MAX_RECENT) : [];
  } catch {
    return [];
  }
}

function remember(origin) {
  try {
    const next = [origin, ...readRecent().filter((s) => s !== origin)].slice(0, MAX_RECENT);
    localStorage.setItem(SERVERS_KEY, JSON.stringify(next));
    localStorage.setItem(LAST_KEY, origin);
  } catch {
    // Without storage the address just is not remembered.
  }
}

function busy(on, text) {
  go.disabled = on;
  input.disabled = on;
  ring.hidden = !on;
  label.textContent = on ? text : 'Connect';
}

function say(text, bad = false) {
  note.textContent = text;
  note.classList.toggle('bad', bad);
}

async function connect(text) {
  const options = candidates(text);
  if (options.length === 0) {
    say('That does not look like an address. Try something like katib.example.com or 192.168.1.20:8420.', true);
    return;
  }
  busy(true, 'Connecting');
  say('');
  for (const origin of options) {
    if (await reachable(origin)) {
      remember(origin);
      const host = new URL(origin).hostname;
      if (origin.startsWith('http://') && !isPrivateHost(host)) {
        say('This address is not encrypted. Anyone between you and the server could read your work.');
        await new Promise((resolve) => setTimeout(resolve, 2500));
      }
      location.href = origin;
      return;
    }
  }
  busy(false);
  say('Could not reach that server. Check the address, and that your phone is on the right network.', true);
}

function showRecent() {
  const servers = readRecent();
  list.replaceChildren();
  recent.hidden = servers.length === 0;
  for (const origin of servers) {
    const item = document.createElement('li');
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = origin.replace(/^https?:\/\//, '');
    button.addEventListener('click', () => {
      input.value = origin;
      void connect(origin);
    });
    item.append(button);
    list.append(item);
  }
}

form.addEventListener('submit', (event) => {
  event.preventDefault();
  void connect(input.value);
});

showRecent();
const last = localStorage.getItem(LAST_KEY);
// Open the last server straight away, unless the person came back here on purpose to change it.
if (last && !location.search.includes('change')) {
  input.value = last;
  void connect(last);
} else if (last) {
  input.value = last;
}
