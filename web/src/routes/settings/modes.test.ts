import { describe, expect, it } from 'vitest';
import { activeMode, blockedBy, MODES } from './modes';

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

describe('blockedBy', () => {
  const docker = from({ 'auth.mode': 'local', 'server.host': '0.0.0.0', 'server.behind_proxy': false });
  const locked = (key: string) =>
    ({ 'auth.mode': 'KATIB_AUTH__MODE', 'server.host': 'KATIB_SERVER__HOST' })[key] ?? null;

  it('names the variables that would refuse the change', () => {
    const alone = MODES.find((m) => m.id === 'alone') as (typeof MODES)[number];
    expect(blockedBy(alone, docker, locked)).toEqual(['KATIB_AUTH__MODE', 'KATIB_SERVER__HOST']);
  });

  it('does not block the mode that is already in force', () => {
    const team = MODES.find((m) => m.id === 'team') as (typeof MODES)[number];
    expect(blockedBy(team, docker, locked)).toEqual([]);
  });

  it('allows a change to a setting nothing has fixed', () => {
    const internet = MODES.find((m) => m.id === 'internet') as (typeof MODES)[number];
    expect(blockedBy(internet, docker, locked)).toEqual([]);
  });

  it('blocks nothing when the environment sets nothing', () => {
    for (const mode of MODES) {
      expect(blockedBy(mode, docker, () => null)).toEqual([]);
    }
  });
});
