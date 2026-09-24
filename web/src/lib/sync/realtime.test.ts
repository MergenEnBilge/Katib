import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { colorFor, initials, Realtime, type ServerEvent } from './realtime';

class FakeSocket {
  static OPEN = 1;
  readyState = 1;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((m: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  send(data: string): void {
    this.sent.push(data);
  }
  close(): void {
    this.onclose?.();
  }
}

describe('initials and colors', () => {
  it('uses the first letters of the first and last name', () => {
    expect(initials('Sam Rivera')).toBe('SR');
    expect(initials('  ada ')).toBe('AD');
    expect(initials('Mary Jane Watson')).toBe('MW');
    expect(initials('')).toBe('?');
  });
  it('gives a person the same color every time', () => {
    expect(colorFor('abc')).toBe(colorFor('abc'));
    expect(colorFor('abc')).toMatch(/^#[0-9A-F]{6}$/);
  });
});

describe('Realtime', () => {
  const sockets: FakeSocket[] = [];

  beforeEach(() => {
    vi.useFakeTimers();
    vi.stubGlobal('WebSocket', FakeSocket);
    sockets.length = 0;
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  function make(events: ServerEvent[], reconnects: { n: number }): Realtime {
    return new Realtime({
      projectId: 'p1',
      onEvent: (e) => events.push(e),
      onReconnect: () => reconnects.n++,
      socket: () => {
        const s = new FakeSocket();
        sockets.push(s);
        return s as unknown as WebSocket;
      },
    });
  }

  it('sends what the person is viewing when the socket opens', () => {
    const rt = make([], { n: 0 });
    rt.setViewing('img1');
    rt.connect();
    sockets[0]?.onopen?.();
    expect(sockets[0]?.sent).toContain(JSON.stringify({ type: 'viewing', image_id: 'img1' }));
  });

  it('passes events on and ignores malformed ones', () => {
    const events: ServerEvent[] = [];
    make(events, { n: 0 }).connect();
    sockets[0]?.onmessage?.({ data: JSON.stringify({ type: 'class.changed' }) });
    sockets[0]?.onmessage?.({ data: 'not json' });
    expect(events).toEqual([{ type: 'class.changed' }]);
  });

  it('reconnects with a delay and asks the app to refetch', () => {
    const reconnects = { n: 0 };
    make([], reconnects).connect();
    sockets[0]?.onopen?.();
    expect(reconnects.n).toBe(0);
    sockets[0]?.onclose?.();
    vi.advanceTimersByTime(999);
    expect(sockets).toHaveLength(1);
    vi.advanceTimersByTime(2);
    expect(sockets).toHaveLength(2);
    sockets[1]?.onopen?.();
    expect(reconnects.n).toBe(1);
  });

  it('stays closed after close()', () => {
    const rt = make([], { n: 0 });
    rt.connect();
    rt.close();
    vi.advanceTimersByTime(60_000);
    expect(sockets).toHaveLength(1);
  });
});
