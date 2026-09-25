import { describe, expect, it } from 'vitest';
import { placeCard, tourSteps } from './steps';

const screen = { w: 1200, h: 800 };
const card = { w: 320, h: 180 };
const ctx = { types: ['box', 'text'], hasImages: true, hasClasses: true, canManage: true, shared: false };
const ids = (name: 'workspace' | 'home' | 'settings', c = ctx) => tourSteps(name, c).map((s) => s.id);

describe('tourSteps', () => {
  it('leaves out steps for shapes the project does not use', () => {
    const list = ids('workspace', { ...ctx, types: ['polygon'] });
    expect(list).not.toContain('draw');
    expect(list).not.toContain('text');
    expect(list).toContain('done');
  });

  it('includes the drawing and text steps when they apply', () => {
    expect(ids('workspace')).toContain('draw');
    expect(ids('workspace')).toContain('text');
  });

  it('points at what is missing first', () => {
    const empty = ids('workspace', { ...ctx, hasImages: false, hasClasses: false });
    expect(empty).toContain('add-pictures');
    expect(empty).toContain('add-class');
    expect(empty).not.toContain('images');
    expect(empty).not.toContain('classes');
    expect(ids('workspace')).toContain('images');
    expect(ids('workspace')).not.toContain('add-pictures');
  });

  it('hides management steps from people who cannot manage', () => {
    const list = ids('workspace', { ...ctx, canManage: false });
    expect(list).not.toContain('export');
    expect(list).not.toContain('split');
  });

  it('mentions the team only on a shared server', () => {
    expect(ids('workspace')).not.toContain('team');
    expect(ids('workspace', { ...ctx, shared: true })).toContain('team');
  });

  it('starts with a welcome and ends with help', () => {
    const all = ids('workspace');
    expect(all[0]).toBe('welcome');
    expect(all.at(-1)).toBe('help');
  });

  it('has short tours for the home page and settings', () => {
    expect(ids('home')[0]).toBe('home-welcome');
    expect(ids('settings')).toContain('settings-save');
    expect(ids('home')).not.toContain('home-inbox');
  });
});

describe('placeCard', () => {
  it('centers a card that has nothing to point at', () => {
    expect(placeCard(null, card, screen)).toEqual({ x: 440, y: 310 });
  });

  it('puts the card to the right of a target on the left edge', () => {
    const place = placeCard({ x: 0, y: 100, w: 280, h: 600 }, card, screen);
    expect(place.x).toBe(294);
    expect(place.y).toBeGreaterThanOrEqual(12);
  });

  it('puts the card to the left of a target on the right edge', () => {
    const place = placeCard({ x: 900, y: 100, w: 300, h: 600 }, card, screen);
    expect(place.x).toBe(900 - 14 - card.w);
  });

  it('goes below a small target in the top bar when there is no side room', () => {
    const narrow = { w: 340, h: 800 };
    const place = placeCard({ x: 100, y: 10, w: 40, h: 30 }, card, narrow);
    expect(place.y).toBe(10 + 30 + 14);
    expect(place.x).toBeLessThanOrEqual(narrow.w - card.w - 12);
  });

  it('never leaves the screen', () => {
    for (const target of [
      { x: 0, y: 0, w: 1200, h: 800 },
      { x: 1180, y: 780, w: 20, h: 20 },
      { x: 0, y: 0, w: 10, h: 10 },
    ]) {
      const p = placeCard(target, card, screen);
      expect(p.x).toBeGreaterThanOrEqual(0);
      expect(p.y).toBeGreaterThanOrEqual(0);
      expect(p.x + card.w).toBeLessThanOrEqual(screen.w);
      expect(p.y + card.h).toBeLessThanOrEqual(screen.h);
    }
  });
});
