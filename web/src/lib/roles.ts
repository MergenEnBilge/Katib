import type { Role } from './api/types';

export const ROLES: { id: Role; label: string }[] = [
  { id: 'owner', label: 'Owner' },
  { id: 'manager', label: 'Manager' },
  { id: 'reviewer', label: 'Reviewer' },
  { id: 'annotator', label: 'Annotator' },
  { id: 'viewer', label: 'Viewer' },
];

const MANAGER_ASSIGNABLE = new Set<string>(['annotator', 'reviewer', 'viewer']);

/** Mirrors the server's rule: owners may do anything; managers only between the junior roles.
 *  `null` stands for "not in the project". */
export function canAssign(actor: string, current: string | null, next: string | null): boolean {
  if (actor === 'owner') return true;
  if (actor === 'manager') return [current, next].every((r) => r === null || MANAGER_ASSIGNABLE.has(r));
  return false;
}

/** The roles `actor` may hand to someone who currently has `current`. */
export function assignableRoles(actor: string, current: string | null): typeof ROLES {
  return ROLES.filter((r) => canAssign(actor, current, r.id));
}

export function roleLabel(role: string): string {
  return ROLES.find((r) => r.id === role)?.label ?? role;
}
