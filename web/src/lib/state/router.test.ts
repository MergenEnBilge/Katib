import { describe, expect, it } from 'vitest';
import { matchRoute } from './router';

const ID = '0195c0de-1234-7abc-8def-0123456789ab';

describe('matchRoute', () => {
  it('matches the home screen', () => {
    expect(matchRoute('/')).toEqual({ name: 'projects' });
    expect(matchRoute('')).toEqual({ name: 'projects' });
  });
  it('matches a workspace by project id', () => {
    expect(matchRoute(`/p/${ID}`)).toEqual({ name: 'workspace', projectId: ID });
    expect(matchRoute(`/p/${ID}/`)).toEqual({ name: 'workspace', projectId: ID });
  });
  it('matches the class gallery', () => {
    expect(matchRoute(`/p/${ID}/gallery`)).toEqual({ name: 'gallery', projectId: ID });
  });
  it('rejects malformed ids and unknown paths', () => {
    expect(matchRoute('/p/abc')).toEqual({ name: 'not-found' });
    expect(matchRoute('/nope')).toEqual({ name: 'not-found' });
  });
});
