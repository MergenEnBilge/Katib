<script lang="ts">
  import TipCard from '../../lib/ui/TipCard.svelte';
  import { Copy, UserPlus, X } from '@lucide/svelte';
  import { api, ApiError } from '../../lib/api/client';
  import type { Activity, Member, PersonBrief, Project, Role } from '../../lib/api/types';
  import { plural, relativeTime } from '../../lib/format';
  import { assignableRoles, canAssign, roleLabel } from '../../lib/roles';
  import { toasts } from '../../lib/state/toast.svelte';
  import Avatar from '../../lib/ui/Avatar.svelte';
  import Button from '../../lib/ui/Button.svelte';
  import Modal from '../../lib/ui/Modal.svelte';

  let {
    project,
    onproject,
    onmembers,
    onclose,
  }: {
    project: Project;
    /** The project changed here (the review setting), so whoever opened this can keep up. */
    onproject?: (project: Project) => void;
    onmembers?: (members: Member[]) => void;
    onclose: () => void;
  } = $props();

  let tab = $state<'members' | 'activity' | 'settings'>('members');
  let members = $state<Member[] | null>(null);
  let error = $state('');

  const me = $derived(project.role ?? 'viewer');
  const canManage = $derived(me === 'owner' || me === 'manager');

  async function loadMembers(): Promise<void> {
    try {
      members = await api.members.list(project.id);
    } catch (err) {
      members = [];
      error = err instanceof ApiError ? err.message : 'Could not load the team.';
    }
  }

  $effect(() => {
    void loadMembers();
  });

  function changed(next: Member[]): void {
    members = next;
    onmembers?.(next);
  }

  // Adding someone who already has an account.
  let search = $state('');
  let found = $state<PersonBrief[]>([]);
  let searched = $state(false);
  let addRole = $state<Role>('annotator');
  let adding = $state<string | null>(null);

  $effect(() => {
    if (!canManage) return;
    const q = search.trim();
    const timer = setTimeout(() => {
      api.members
        .addable(project.id, q)
        .then((people) => {
          found = people;
          searched = true;
        })
        .catch(() => (found = []));
    }, 200);
    return () => clearTimeout(timer);
  });

  async function add(person: PersonBrief): Promise<void> {
    adding = person.id;
    error = '';
    try {
      changed(await api.members.set(project.id, person.id, addRole));
      found = found.filter((p) => p.id !== person.id);
      toasts.show(`${person.name} can now work on this project as ${roleLabel(addRole).toLowerCase()}.`);
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not add that person.';
    } finally {
      adding = null;
    }
  }

  async function setRole(userId: string, role: Role): Promise<void> {
    error = '';
    try {
      changed(await api.members.set(project.id, userId, role));
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not change the role.';
      await loadMembers();
    }
  }

  let removing = $state<string | null>(null);

  async function remove(userId: string, name: string): Promise<void> {
    error = '';
    try {
      changed(await api.members.remove(project.id, userId));
      toasts.show(`${name} no longer has access to this project.`);
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not remove that person.';
    } finally {
      removing = null;
    }
  }

  // Inviting someone who has no account yet.
  let inviteRole = $state<Exclude<Role, 'owner'>>('annotator');
  let inviteTo = $state<'computer' | 'phone'>('computer');
  let link = $state('');
  let addressMissing = $state(false);
  let inviting = $state(false);

  async function invite(): Promise<void> {
    inviting = true;
    error = '';
    try {
      const made = await api.auth.createInvite(project.id, inviteRole);
      // The server knows an address other people can reach. Ours may just say localhost.
      link = made.url || `${location.origin}${made.path}`;
      addressMissing = !made.url;
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not create the invite.';
    } finally {
      inviting = false;
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

  let activity = $state<Activity[] | null>(null);

  $effect(() => {
    if (tab === 'activity' && activity === null) {
      api.work
        .activity(project.id)
        .then((a) => (activity = a))
        .catch(() => (activity = []));
    }
  });

  async function toggleReview(enabled: boolean): Promise<void> {
    try {
      onproject?.(await api.work.setReview(project.id, enabled));
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

  const handOut = $derived(assignableRoles(me, null));
  const inviteRoles = $derived(handOut.filter((r) => r.id !== 'owner') as { id: Exclude<Role, 'owner'>; label: string }[]);
</script>

<Modal title="Team" description="Who can work on {project.name}, what they did, and how review works." width={600} {onclose}>
  <TipCard id="dialog:team" />
  <div class="tabs" role="tablist">
    {#each [['members', 'Members'], ['activity', 'Activity'], ['settings', 'Settings']] as const as [id, label] (id)}
      <button type="button" role="tab" aria-selected={tab === id} class:active={tab === id} onclick={() => (tab = id)}>{label}</button>
    {/each}
  </div>

  {#if error}<p class="error" role="alert">{error}</p>{/if}

  {#if tab === 'members'}
    {#if canManage}
      <section class="add" aria-labelledby="add-title">
        <p class="label" id="add-title">Add people who already have an account</p>
        <div class="row">
          <input type="search" placeholder="Search by name or email" aria-label="Search people to add" bind:value={search} />
          <select aria-label="Role for the people you add" bind:value={addRole}>
            {#each handOut as r (r.id)}<option value={r.id}>{r.label}</option>{/each}
          </select>
        </div>
        {#if found.length}
          <ul class="found">
            {#each found as person (person.id)}
              <li>
                <Avatar name={person.name} userId={person.id} size={24} />
                <span class="who"><strong>{person.name}</strong><small>{person.email}</small></span>
                <Button loading={adding === person.id} onclick={() => add(person)}>
                  <UserPlus size={14} />Add
                </Button>
              </li>
            {/each}
          </ul>
        {:else if searched}
          <p class="note">
            {search.trim()
              ? 'Nobody else matches. Invite them below if they have no account yet.'
              : 'Everyone with an account is already on this project.'}
          </p>
        {/if}
      </section>
    {/if}

    <p class="label">On this project</p>
    {#if members === null}
      <div class="sk" aria-busy="true"></div>
    {:else}
      <ul class="people">
        {#each members as m (m.user.id)}
          <li>
            <Avatar name={m.user.name} userId={m.user.id} size={28} />
            <span class="who"><strong>{m.user.name}</strong><small>{m.user.email}</small></span>
            {#if removing === m.user.id}
              <span class="confirm">
                <span>Remove {m.user.name}?</span>
                <Button variant="danger" onclick={() => remove(m.user.id, m.user.name)}>Remove</Button>
                <Button onclick={() => (removing = null)}>Keep</Button>
              </span>
            {:else if assignableRoles(me, m.role).some((r) => r.id !== m.role)}
              <select aria-label="Role of {m.user.name}" value={m.role} onchange={(e) => setRole(m.user.id, e.currentTarget.value as Role)}>
                {#each assignableRoles(me, m.role) as r (r.id)}<option value={r.id}>{r.label}</option>{/each}
              </select>
              {#if canAssign(me, m.role, null)}
                <button type="button" class="x" aria-label="Remove {m.user.name}" onclick={() => (removing = m.user.id)}><X size={14} /></button>
              {/if}
            {:else}
              <span class="role">{roleLabel(m.role)}</span>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}

    {#if canManage}
      <div class="invite">
        <p class="label">Invite someone without an account</p>
        <div class="row">
          <select aria-label="Role for the invited person" bind:value={inviteRole}>
            {#each inviteRoles as r (r.id)}<option value={r.id}>{r.label}</option>{/each}
          </select>
          <select aria-label="What they will use" bind:value={inviteTo}>
            <option value="computer">On a computer</option>
            <option value="phone">On a phone</option>
          </select>
          <Button disabled={inviting} onclick={invite}>Create invite link</Button>
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
          <p class="note">
            The link works once and expires in 7 days. Someone who already has an account can open
            it too, and just signs in.
          </p>
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
        checked={project.review_enabled ?? false}
        disabled={!canManage}
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

  .add {
    margin-block-end: var(--space-4);
    padding-block-end: var(--space-3);
    border-block-end: 1px solid var(--border);
  }

  .people li,
  .found li {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding-block: var(--space-2);
    border-block-end: 1px solid var(--border);
  }

  .found li:last-child {
    border-block-end: 0;
  }

  .who {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: 0;
  }

  .who small {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
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

  .confirm {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-small);
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

  .row input {
    flex: 1;
    min-width: 0;
  }

  .row input[readonly] {
    font-family: var(--font-mono);
    font-size: var(--text-small);
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

  @media (max-width: 699px) {
    .row {
      flex-wrap: wrap;
    }
  }
</style>
