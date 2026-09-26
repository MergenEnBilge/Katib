<script lang="ts">
  import TipCard from '../../lib/ui/TipCard.svelte';
  import { Copy, X } from '@lucide/svelte';
  import { api, ApiError } from '../../lib/api/client';
  import type { Activity, Role } from '../../lib/api/types';
  import { plural, relativeTime } from '../../lib/format';
  import { toasts } from '../../lib/state/toast.svelte';
  import type { Workspace } from '../../lib/state/workspace.svelte';
  import Avatar from '../../lib/ui/Avatar.svelte';
  import Button from '../../lib/ui/Button.svelte';
  import Modal from '../../lib/ui/Modal.svelte';

  let { ws, onclose }: { ws: Workspace; onclose: () => void } = $props();

  let tab = $state<'members' | 'activity' | 'settings'>('members');
  let inviteRole = $state<Exclude<Role, 'owner'>>('annotator');
  let inviteTo = $state<'computer' | 'phone'>('computer');
  let link = $state('');
  let addressMissing = $state(false);
  let error = $state('');
  let activity = $state<Activity[] | null>(null);
  let busy = $state(false);

  const roles: { id: Role; label: string }[] = [
    { id: 'owner', label: 'Owner' },
    { id: 'manager', label: 'Manager' },
    { id: 'annotator', label: 'Annotator' },
    { id: 'reviewer', label: 'Reviewer' },
    { id: 'viewer', label: 'Viewer' },
  ];

  const isOwner = $derived(ws.role === 'owner');

  $effect(() => {
    if (tab === 'activity' && activity === null) {
      api.work
        .activity(ws.projectId)
        .then((a) => (activity = a))
        .catch(() => (activity = []));
    }
  });

  async function invite(): Promise<void> {
    busy = true;
    error = '';
    try {
      const made = await api.auth.createInvite(ws.projectId, inviteRole);
      // The server knows an address other people can reach. Ours may just say localhost.
      link = made.url || `${location.origin}${made.path}`;
      addressMissing = !made.url;
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not create the invite.';
    } finally {
      busy = false;
    }
  }

  async function copy(): Promise<void> {
    try {
      await navigator.clipboard.writeText(link);
      toasts.show('Invite link copied.');
    } catch {
      toasts.show('Copy the link from the box.');
    }
  }

  async function setRole(userId: string, role: Role): Promise<void> {
    try {
      ws.members = await api.members.set(ws.projectId, userId, role);
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not change the role.';
      await ws.loadMembers();
    }
  }

  async function remove(userId: string, name: string): Promise<void> {
    try {
      ws.members = await api.members.remove(ws.projectId, userId);
      toasts.show(`${name} was removed from this project.`);
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not remove that person.';
    }
  }

  async function toggleReview(enabled: boolean): Promise<void> {
    try {
      const project = await api.work.setReview(ws.projectId, enabled);
      ws.project = project;
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not change that setting.';
    }
  }

  function describe(a: Activity): string {
    const n = typeof a.payload.count === 'number' ? a.payload.count : 0;
    switch (a.verb) {
      case 'marked_done':
        return 'marked an image as done';
      case 'marked_approved':
        return 'approved an image';
      case 'marked_rejected':
        return 'sent an image back';
      case 'marked_in_progress':
        return 'reopened an image';
      case 'commented':
        return 'commented on an image';
      case 'assigned':
        return `assigned ${plural(n, 'image')}`;
      default:
        return a.verb.replaceAll('_', ' ');
    }
  }
</script>

<Modal title="Team" description="Who works on this project, what they did, and how review works." width={600} {onclose}>
  <TipCard id="dialog:team" />
  <div class="tabs" role="tablist">
    {#each [['members', 'Members'], ['activity', 'Activity'], ['settings', 'Settings']] as const as [id, label] (id)}
      <button type="button" role="tab" aria-selected={tab === id} class:active={tab === id} onclick={() => (tab = id)}>{label}</button>
    {/each}
  </div>

  {#if error}<p class="error" role="alert">{error}</p>{/if}

  {#if tab === 'members'}
    <ul class="people">
      {#each ws.members as m (m.user.id)}
        <li>
          <Avatar name={m.user.name} userId={m.user.id} size={28} />
          <span class="who"><strong>{m.user.name}</strong><small>{m.user.email}</small></span>
          {#if isOwner}
            <select aria-label="Role of {m.user.name}" value={m.role} onchange={(e) => setRole(m.user.id, e.currentTarget.value as Role)}>
              {#each roles as r (r.id)}<option value={r.id}>{r.label}</option>{/each}
            </select>
            <button type="button" class="x" aria-label="Remove {m.user.name}" onclick={() => remove(m.user.id, m.user.name)}><X size={14} /></button>
          {:else}
            <span class="role">{roles.find((r) => r.id === m.role)?.label}</span>
          {/if}
        </li>
      {/each}
    </ul>

    {#if ws.canManage}
      <div class="invite">
        <p class="label">Invite someone</p>
        <div class="row">
          <select aria-label="Role for the invited person" bind:value={inviteRole}>
            <option value="annotator">Annotator</option>
            <option value="reviewer">Reviewer</option>
            <option value="manager">Manager</option>
            <option value="viewer">Viewer</option>
          </select>
          <select aria-label="What they will use" bind:value={inviteTo}>
            <option value="computer">On a computer</option>
            <option value="phone">On a phone</option>
          </select>
          <Button disabled={busy} onclick={invite}>Create invite link</Button>
        </div>
        {#if link}
          {#if addressMissing}
            <p class="warn" role="alert">
              This link carries the address in your own address bar, which nobody else can open.
              Click your name at the bottom of the sidebar, tell Katib its address, and make the
              link again.
            </p>
          {/if}
          {#if inviteTo === 'phone'}
            <div class="scan">
              <img src={api.share.qrUrl(link)} alt="Code to join this project" width="160" height="160" />
              <div>
                <p>Have them point their phone camera at this code.</p>
                <p class="note">
                  Android offers to open the Katib app, or to download it first. On an iPhone the
                  page works in Safari.
                </p>
              </div>
            </div>
          {/if}
          <div class="row">
            <input readonly value={link} aria-label="Invite link" onfocus={(e) => e.currentTarget.select()} />
            <Button onclick={copy}><Copy size={16} />Copy</Button>
          </div>
          <p class="note">The link works once and expires in 7 days. Send it only to the person you are inviting.</p>
        {/if}
      </div>
    {/if}
  {:else if tab === 'activity'}
    {#if activity === null}
      <div class="sk" aria-busy="true"></div>
    {:else if activity.length === 0}
      <p class="note">Nothing has happened yet. Finishing images, reviews and comments appear here.</p>
    {:else}
      <ul class="feed">
        {#each activity as a (a.id)}
          <li><span><strong>{a.who}</strong> {describe(a)}</span><small>{relativeTime(a.created_at)}</small></li>
        {/each}
      </ul>
    {/if}
  {:else}
    <label class="toggle">
      <input
        type="checkbox"
        checked={ws.project?.review_enabled ?? false}
        disabled={!ws.canManage}
        onchange={(e) => toggleReview(e.currentTarget.checked)}
      />
      <span>
        <strong>Review finished images</strong>
        <small>Images marked as done wait for a reviewer to approve them or send them back with a comment.</small>
      </span>
    </label>
  {/if}

  {#snippet footer()}
    <Button variant="primary" onclick={onclose}>Done</Button>
  {/snippet}
</Modal>

<style>
  .tabs {
    display: flex;
    gap: var(--space-1);
    margin-block-end: var(--space-3);
    padding: 2px;
    width: fit-content;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius-group);
  }

  .tabs button {
    height: 28px;
    padding-inline: var(--space-3);
    color: var(--text-2);
    background: transparent;
    border: 0;
    border-radius: var(--radius-control);
    cursor: pointer;
  }

  .tabs button.active {
    color: var(--accent-text);
    background: var(--accent-muted);
  }

  .error {
    margin: 0 0 var(--space-2);
    color: var(--danger);
    font-size: var(--text-small);
  }

  ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .people li {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding-block: var(--space-2);
    border-block-end: 1px solid var(--border);
  }

  .who {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: 0;
  }

  small,
  .note {
    color: var(--text-2);
    font-size: var(--text-small);
  }

  .note {
    margin: var(--space-2) 0 0;
  }

  select,
  input:not([type='checkbox']) {
    height: var(--h-button-sm);
    padding-inline: var(--space-2);
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
  }

  .x {
    display: grid;
    place-items: center;
    width: var(--h-icon-sm);
    height: var(--h-icon-sm);
    color: var(--text-2);
    background: transparent;
    border: 0;
    cursor: pointer;
  }

  .role {
    color: var(--text-2);
    font-size: var(--text-small);
  }

  .invite {
    margin-block-start: var(--space-4);
  }

  .label {
    margin: 0 0 var(--space-2);
    font-size: var(--text-overline);
    font-weight: 500;
    color: var(--text-3);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .row {
    display: flex;
    gap: var(--space-2);
    margin-block-end: var(--space-2);
  }

  .warn {
    margin: 0 0 var(--space-2);
    color: var(--text-2);
    font-size: var(--text-small);
  }

  .scan {
    display: flex;
    gap: var(--space-3);
    align-items: flex-start;
    padding: var(--space-3);
    margin-block-end: var(--space-2);
    background: var(--surface-2);
    border-radius: var(--radius-card);
  }

  .scan img {
    flex: none;
    background: #fff;
    border: 1px solid var(--border);
    border-radius: var(--radius-control);
  }

  .scan p {
    margin: 0;
  }

  .row input {
    flex: 1;
    min-width: 0;
    font-family: var(--font-mono);
    font-size: var(--text-small);
  }

  .feed li {
    display: flex;
    justify-content: space-between;
    gap: var(--space-3);
    padding-block: var(--space-2);
    border-block-end: 1px solid var(--border);
  }

  .toggle {
    display: flex;
    gap: var(--space-3);
    align-items: flex-start;
  }

  .toggle span {
    display: flex;
    flex-direction: column;
  }

  .sk {
    height: 96px;
    background: var(--surface-1);
    border-radius: var(--radius-card);
  }
</style>
