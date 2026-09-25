import { beforeEach, describe, expect, it } from 'vitest';
import { i18n, LOCALES, t, tp } from './index.svelte';
import { pseudo } from './pseudo';

describe('translating', () => {
  beforeEach(() => {
    localStorage.clear();
    i18n.setLocale('en');
  });

  it('fills in named values', () => {
    expect(t('projects.done', { done: 3, total: 10 })).toBe('3 of 10 done');
  });

  it('leaves a marker alone when its value is missing, so a gap is easy to see', () => {
    expect(t('projects.noMatch')).toContain('{query}');
  });

  it('picks the singular or plural form', () => {
    expect(tp('projects.images', 1)).toBe('1 image');
    expect(tp('projects.images', 2)).toBe('2 images');
    expect(tp('projects.images', 1200)).toBe('1,200 images');
  });

  it('falls back to English for a key a language has not translated', () => {
    LOCALES.push({ code: 'xx', name: 'Test', dir: 'ltr', hidden: true, messages: { 'nav.inbox': 'Postfach' } });
    i18n.setLocale('xx');
    expect(t('nav.inbox')).toBe('Postfach');
    expect(t('nav.projects')).toBe('Projects');
    LOCALES.pop();
  });
});

describe('choosing a language', () => {
  beforeEach(() => {
    localStorage.clear();
    i18n.setLocale('en');
  });

  it('starts in English when nothing says otherwise', () => {
    i18n.init('', ['fr-FR']);
    expect(i18n.locale).toBe('en');
  });

  it('follows ?lang= and remembers it', () => {
    i18n.init('?lang=qps-plocm', []);
    expect(i18n.locale).toBe('qps-plocm');
    expect(localStorage.getItem('katib.locale')).toBe('qps-plocm');
    // A later visit with no ?lang= uses the saved choice.
    i18n.setLocale('en');
    localStorage.setItem('katib.locale', 'qps-plocm');
    i18n.init('', []);
    expect(i18n.locale).toBe('qps-plocm');
  });

  it('turns the page around for a right-to-left language and back again', () => {
    i18n.setLocale('qps-plocm');
    expect(document.documentElement.dir).toBe('rtl');
    expect(i18n.dir).toBe('rtl');
    i18n.setLocale('en');
    expect(document.documentElement.dir).toBe('ltr');
    expect(document.documentElement.lang).toBe('en');
  });

  it('does not list the test languages as choices', () => {
    expect(i18n.choices.map((l) => l.code)).toEqual(['en']);
  });
});

describe('pseudo-localization', () => {
  it('accents letters, pads, and keeps markers intact', () => {
    const text = pseudo('Edited {when}');
    expect(text).toMatch(/^\[.*\]$/);
    expect(text).toContain('{when}');
    expect(text).not.toContain('Edited');
    expect(text.length).toBeGreaterThan('Edited {when}'.length);
  });

  it('gives every English message a pseudo version', () => {
    const pseudoLocale = LOCALES.find((l) => l.code === 'qps-ploc');
    expect(Object.keys(pseudoLocale?.messages ?? {}).length).toBeGreaterThan(20);
    expect(pseudoLocale?.messages['nav.inbox']).toBe(pseudo('Inbox'));
  });
});
