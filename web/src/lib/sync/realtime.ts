export interface PresenceUser {
  user_id: string;
  name: string;
  image_id: string | null;
}

export type ServerEvent =
  | { type: 'presence'; users: PresenceUser[] }
  | { type: 'annotation.changed'; image_id: string; user_id: string }
  | { type: 'image.locked'; image_id: string; user_id: string; name: string | null }
  | { type: 'image.unlocked'; image_id: string }
  | { type: 'image.status'; image_id: string; status: string }
  | { type: 'class.changed' }
  | { type: 'pong' };

const RETRY_MS = [1000, 2000, 5000, 10000, 20000];
const PING_MS = 25_000;

export interface RealtimeOptions {
  projectId: string;
  onEvent(event: ServerEvent): void;
  /** Called after a reconnect. Events are hints, so the app should refetch what it shows. */
  onReconnect(): void;
  socket?: (url: string) => WebSocket;
}

/** Keeps one WebSocket per project alive, and reconnects with a growing delay. */
export class Realtime {
  private ws: WebSocket | null = null;
  private attempts = 0;
  private closed = false;
  private timer: ReturnType<typeof setTimeout> | undefined;
  private ping: ReturnType<typeof setInterval> | undefined;
  private viewing: string | null = null;
  private everOpened = false;

  constructor(private readonly opts: RealtimeOptions) {}

  get url(): string {
    const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
    return `${scheme}://${location.host}/api/v1/ws?project=${encodeURIComponent(this.opts.projectId)}`;
  }

  connect(): void {
    this.closed = false;
    this.open();
  }

  private open(): void {
    const make = this.opts.socket ?? ((u: string) => new WebSocket(u));
    const ws = make(this.url);
    this.ws = ws;
    ws.onopen = () => {
      this.attempts = 0;
      if (this.everOpened) this.opts.onReconnect();
      this.everOpened = true;
      this.send({ type: 'viewing', image_id: this.viewing });
      clearInterval(this.ping);
      this.ping = setInterval(() => this.send({ type: 'ping' }), PING_MS);
    };
    ws.onmessage = (message) => {
      try {
        this.opts.onEvent(JSON.parse(String(message.data)) as ServerEvent);
      } catch {
        // A malformed message is ignored. The next event or refetch corrects the view.
      }
    };
    ws.onclose = () => {
      clearInterval(this.ping);
      if (this.closed) return;
      const wait = RETRY_MS[Math.min(this.attempts++, RETRY_MS.length - 1)] as number;
      this.timer = setTimeout(() => this.open(), wait);
    };
  }

  /** Tell everyone which image this person has open. */
  setViewing(imageId: string | null): void {
    this.viewing = imageId;
    this.send({ type: 'viewing', image_id: imageId });
  }

  private send(message: object): void {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(message));
  }

  close(): void {
    this.closed = true;
    clearTimeout(this.timer);
    clearInterval(this.ping);
    this.ws?.close();
  }
}

/** An ISO timestamp `ms` milliseconds from now. Plain helper so state files stay free of Date. */
export function isoIn(ms: number): string {
  return new Date(Date.now() + ms).toISOString();
}

/** Two-letter initials for the presence avatar. */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  const first = parts[0] as string;
  const last = parts.length > 1 ? (parts[parts.length - 1] as string) : '';
  return ((first[0] ?? '') + (last[0] ?? first[1] ?? '')).toUpperCase();
}

const PALETTE = ['#4C8DF6', '#E86FB0', '#F2994A', '#2EC4D6', '#8B6CF0', '#F2C94C', '#FF8A65', '#5B7CFA'];

/** A fixed color per person, so the same avatar looks the same on every screen. */
export function colorFor(userId: string): string {
  let hash = 0;
  for (const ch of userId) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
  return PALETTE[hash % PALETTE.length] as string;
}
