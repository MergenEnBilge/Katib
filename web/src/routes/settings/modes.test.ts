import { describe, expect, it } from 'vitest';
import { activeMode, MODES } from './modes';

const from = (values: Record<string, unknown>) => (key: string) => values[key];

describe('activeMode', () => {
  it('recognises each mode from the settings it sets', () => {
    for (const mode of MODES) {
      expect(activeMode(from(mode.values))).toBe(mode.id);
    }
  });

  it('is nobody when the settings are a mix', () => {
    expect(activeMode(from({ 'auth.mode': 'none', 'server.host': '0.0.0.0' }))).toBeNull();
  });

  it('tells a network team apart from one behind a proxy', () => {
    const team = MODES.find((m) => m.id === 'team');
    const internet = MODES.find((m) => m.id === 'internet');
    expect(team?.values['server.behind_proxy']).toBe(false);
    expect(internet?.values['server.behind_proxy']).toBe(true);
  });

  it('never leaves accounts off on a shared address', () => {
    for (const mode of MODES) {
      if (mode.values['server.host'] !== '127.0.0.1') {
        expect(mode.values['auth.mode']).toBe('local');
      }
    }
  });
});
