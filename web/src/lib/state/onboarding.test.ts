import { describe, expect, it } from 'vitest';
import { complete, finished, parse, STEPS } from './onboarding';

describe('onboarding progress', () => {
  it('starts empty', () => {
    expect(parse(null)).toEqual({ done: [], dismissed: false });
  });

  it('reads what it saved', () => {
    expect(parse('{"done":["project","images"],"dismissed":true}')).toEqual({
      done: ['project', 'images'],
      dismissed: true,
    });
  });

  it('ignores junk in storage', () => {
    expect(parse('not json')).toEqual({ done: [], dismissed: false });
    expect(parse('{"done":["project","launch-rockets",7,"project"],"dismissed":"yes"}')).toEqual({
      done: ['project'],
      dismissed: false,
    });
  });

  it('ticks a step once', () => {
    const one = complete({ done: [], dismissed: false }, 'class');
    expect(complete(one, 'class')).toBe(one);
    expect(one.done).toEqual(['class']);
  });

  it('is finished only when every step is done', () => {
    const all = { done: STEPS.map((s) => s.id), dismissed: false };
    expect(finished(all)).toBe(true);
    expect(finished({ ...all, done: all.done.slice(1) })).toBe(false);
  });
});
