import { describe, expect, it } from 'vitest';
import { assignableRoles, canAssign } from './roles';

describe('canAssign', () => {
  it('lets an owner do anything', () => {
    expect(canAssign('owner', null, 'owner')).toBe(true);
    expect(canAssign('owner', 'manager', null)).toBe(true);
  });

  it('keeps a manager to annotators, reviewers and viewers', () => {
    expect(canAssign('manager', null, 'annotator')).toBe(true);
    expect(canAssign('manager', 'viewer', 'reviewer')).toBe(true);
    expect(canAssign('manager', 'annotator', null)).toBe(true);
    expect(canAssign('manager', null, 'manager')).toBe(false);
    expect(canAssign('manager', 'owner', null)).toBe(false);
    expect(canAssign('manager', 'manager', 'viewer')).toBe(false);
  });

  it('gives everyone else nothing', () => {
    expect(canAssign('annotator', null, 'viewer')).toBe(false);
    expect(canAssign('viewer', null, 'viewer')).toBe(false);
  });

  it('lists what a manager can hand out', () => {
    expect(assignableRoles('manager', null).map((r) => r.id)).toEqual(['reviewer', 'annotator', 'viewer']);
  });
});
