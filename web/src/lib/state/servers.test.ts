import { describe, expect, it } from 'vitest';
import { cleanServerUrl } from './servers';

describe('cleanServerUrl', () => {
  it('adds http when the scheme is missing', () => {
    expect(cleanServerUrl('192.168.1.4:8420')).toBe('http://192.168.1.4:8420');
  });

  it('keeps https and drops any path', () => {
    expect(cleanServerUrl('https://katib.example.com/projects/1')).toBe('https://katib.example.com');
  });

  it('refuses empty input and other schemes', () => {
    expect(cleanServerUrl('   ')).toBeNull();
    expect(cleanServerUrl('javascript:alert(1)')).toBeNull();
    expect(cleanServerUrl('ftp://files.example.com')).toBeNull();
  });
});
