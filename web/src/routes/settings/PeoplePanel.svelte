<script lang="ts">
  // Accounts on this server: who has one, who is an administrator, and who has been shut out.
  // Invites are the usual way in, but a team that already knows who is joining would rather hand
  // out a login than send seven links.
  import { FolderKanban, KeyRound, ShieldCheck, UserPlus, X } from '@lucide/svelte';
  import { api, ApiError } from '../../lib/api/client';
  import type { Person, Project, Role, UserProject } from '../../lib/api/types';
  import { ROLES, roleLabel } from '../../lib/roles';
  import { session } from '../../lib/state/session.svelte';
  import { toasts } from '../../lib/state/toast.svelte';
  import Button from '../../lib/ui/Button.svelte';
  import Callout from '../../lib/ui/Callout.svelte';
  import TextField from '../../lib/ui/TextField.svelte';

  let people = $state<Person[] | null>(null);
  let error = $state('');
  let busy = $state(false);

  let adding = $state(false);
  let email = $state('');
  let name = $state('');
  let password = $state('');
  let isAdmin = $state(false);

  let resetting = $state<Person | null>(null);
  let newPassword = $state('');

  // Which projects each person is on, opened one person at a time.
  let allProjects = $state<Project[] | null>(null);
  let projectsFor = $state<Person | null>(null);
  let theirs = $state<UserProject[] | null>(null);
  let pickProject = $state('');
  let pickRole = $state<Role>('annotator');
  /** The project, if any, a new account goes straight onto. */
  let newProject = $state('');
  let newRole = $state<Role>('annotator');

  function loadProjects(): void {
    if (allProjects !== null) return;
    api.projects
      .list()
      .then((list) => (allProjects = list))
      .catch(() => (allProjects = []));
  }

  async function showProjects(person: Person): Promise<void> {
    if (projectsFor?.id === person.id) {
      projectsFor = null;
      return;
    }
    projectsFor = person;
    theirs = null;
    pickProject = '';
    loadProjects();
    try {
      theirs = await api.users.projects(person.id);
    } catch (err) {
      failed(err, 'Could not load their projects.');
      theirs = [];
    }
  }

  const notYetOn = $derived(
    (allProjects ?? []).filter((p) => !(theirs ?? []).some((t) => t.project_id === p.id)),
  );

  async function addTo(person: Person): Promise<void> {
    if (!pickProject) return;
    error = '';
    try {
      await api.members.set(pickProject, person.id, pickRole);
      theirs = await api.users.projects(person.id);
      pickProject = '';
    } catch (err) {
      failed(err, 'Could not add them to that project.');
    }
  }

  async function removeFrom(person: Person, item: UserProject): Promise<void> {
    error = '';
    try {
      await api.members.remove(item.project_id, person.id);
      theirs = (theirs ?? []).filter((t) => t.project_id !== item.project_id);
      toasts.show(`${person.name} no longer has access to ${item.name}.`);
    } catch (err) {
      failed(err, 'Could not take them off that project.');
    }
  }

  function load(): void {
    api.users
      .list()
      .then((list) => (people = list))
      .catch((err: unknown) => {
        error = err instanceof ApiError ? err.message : 'Could not load the accounts.';
        people = [];
      });
  }

  $effect(load);

  function failed(err: unknown, fallback: string): void {
    error = err instanceof ApiError ? err.message : fallback;
  }

  function replace(person: Person): void {
    people = (people ?? []).map((p) => (p.id === person.id ? person : p));
  }

  async function add(): Promise<void> {
    busy = true;
    error = '';
    try {
      const made = await api.users.create(email.trim(), name.trim(), password, isAdmin);
      people = [...(people ?? []), made];
      const project = (allProjects ?? []).find((p) => p.id === newProject);
      if (project) await api.members.set(project.id, made.id, newRole);
      toasts.show(
        project
          ? `${made.name} can sign in now, and will find ${project.name} waiting.`
          : `${made.name} can sign in now.`,
      );
      adding = false;
      email = '';
      name = '';
      password = '';
      isAdmin = false;
      newProject = '';
    } catch (err) {
      failed(err, 'Could not create that account.');
    } finally {
      busy = false;
    }
  }

  async function reset(): Promise<void> {
    const person = resetting;
    if (!person) return;
    busy = true;
    error = '';
    try {
      replace(await api.users.setPassword(person.id, newPassword));
      toasts.show(`${person.name} has a new password. Tell them what it is.`);
      resetting = null;
      newPassword = '';
    } catch (err) {
      failed(err, 'Could not change that password.');
    } finally {
      busy = false;
    }
  }

  async function toggleAdmin(person: Person): Promise<void> {
    error = '';
    try {
      replace(await api.users.setAdmin(person.id, !person.is_admin));
    } catch (err) {
      failed(err, 'Could not change that.');
    }
  }

  async function toggleAccess(person: Person): Promise<void> {
    error = '';
    try {
      replace(await api.users.setDisabled(person.id, !person.disabled));
    } catch (err) {
      failed(err, 'Could not change that.');
    }
  }
</script>

<h2 id="section-title">People</h2>
<p class="lead">Everyone with an account on this server.</p>

{#if session.mode !== 'local'}
  <Callout>
    Katib has no accounts at the moment, so there is nobody to manage. Choose a way of sharing under
    Sharing to turn them on.
  </Callout>
{:else}
  {#if error}<Callout tone="danger">{error}</Callout>{/if}

  {#if people === null}
    <div class="sk" aria-busy="true"></div>
  {:else}
    <ul class="people">
      {#each people as person (person.id)}
        <li class:off={person.disabled}>
          <span class="who">
            <strong>{person.name}</strong>
            <small>{person.email}</small>
          </span>
          {#if person.is_admin}<span class="tag"><ShieldCheck size={13} />Administrator</span>{/if}
          {#if person.disabled}<span class="tag off">Shut out</span>{/if}
          <button
            type="button"
            aria-expanded={projectsFor?.id === person.id}
            onclick={() => showProjects(person)}
          >
            <FolderKanban size={14} />Projects
          </button>
          <button type="button" onclick={() => (resetting = person)}>
            <KeyRound size={14} />New password
          </button>
          <button type="button" onclick={() => toggleAdmin(person)}>
            {person.is_admin ? 'Make an ordinary member' : 'Make an administrator'}
          </button>
          <button type="button" onclick={() => toggleAccess(person)}>
            {person.disabled ? 'Let back in' : 'Shut out'}
          </button>
          {#if projectsFor?.id === person.id}
            <div class="theirs" aria-label="Projects {person.name} is on">
              {#if person.is_admin}
                <p class="hint">An administrator can open every project, whether listed here or not.</p>
              {/if}
              {#if theirs === null}
                <div class="sk small" aria-busy="true"></div>
              {:else if theirs.length === 0}
                <p class="hint">{person.name} is not on any project yet.</p>
              {:else}
                <ul>
                  {#each theirs as item (item.project_id)}
                    <li>
                      <span class="pname">{item.name}</span>
                      <span class="prole">{roleLabel(item.role)}</span>
                      <button
                        type="button"
                        class="x"
                        aria-label="Take {person.name} off {item.name}"
                        onclick={() => removeFrom(person, item)}><X size={14} /></button
                      >
                    </li>
                  {/each}
                </ul>
              {/if}
              {#if notYetOn.length}
                <div class="row">
                  <select aria-label="Project to add {person.name} to" bind:value={pickProject}>
                    <option value="">Add to a project…</option>
                    {#each notYetOn as p (p.id)}<option value={p.id}>{p.name}</option>{/each}
                  </select>
                  <select aria-label="Their role there" bind:value={pickRole}>
                    {#each ROLES as r (r.id)}<option value={r.id}>{r.label}</option>{/each}
                  </select>
                  <Button disabled={!pickProject} onclick={() => addTo(person)}>Add</Button>
                </div>
              {/if}
            </div>
          {/if}
        </li>
      {/each}
    </ul>

    {#if resetting}
      <div class="form">
        <p class="label">A new password for {resetting.name}</p>
        <p class="hint">
          They are signed out everywhere as soon as you save this, and will need the new password.
        </p>
        <div class="row">
          <TextField label="Password" bind:value={newPassword} onenter={reset} />
          <Button variant="primary" loading={busy} onclick={reset}>Save</Button>
          <Button
            onclick={() => {
              resetting = null;
              newPassword = '';
            }}>Cancel</Button
          >
        </div>
      </div>
    {/if}

    {#if adding}
      <div class="form">
        <p class="label">A new account</p>
        <div class="row">
          <TextField label="Email" bind:value={email} placeholder="someone@example.com" />
          <TextField label="Name" bind:value={name} placeholder="Their name" />
          <TextField label="Password" bind:value={password} onenter={add} />
        </div>
        <label class="check">
          <input type="checkbox" bind:checked={isAdmin} />
          <span>An administrator, who can change settings and manage everyone</span>
        </label>
        {#if !isAdmin && allProjects?.length}
          <div class="row">
            <select aria-label="Project they start on" bind:value={newProject}>
              <option value="">On no project yet</option>
              {#each allProjects as p (p.id)}<option value={p.id}>{p.name}</option>{/each}
            </select>
            {#if newProject}
              <select aria-label="Their role on that project" bind:value={newRole}>
                {#each ROLES as r (r.id)}<option value={r.id}>{r.label}</option>{/each}
              </select>
            {/if}
          </div>
        {/if}
        <div class="row">
          <Button variant="primary" loading={busy} onclick={add}>Create the account</Button>
          <Button onclick={() => (adding = false)}>Cancel</Button>
        </div>
        <p class="hint">
          Tell them the password yourself. Katib sends no email, so nothing leaves this server.
        </p>
      </div>
    {:else}
      <Button
        onclick={() => {
          adding = true;
          loadProjects();
        }}><UserPlus size={16} />Add someone</Button
      >
    {/if}

    <p class="hint">
      Shutting someone out keeps their work and their name on it, and signs them out at once.
      Katib has no way to delete a person, because their annotations would lose their author.
    </p>
  {/if}
{/if}

<style>
  h2 {
    margin: 0 0 var(--space-1);
    font-size: var(--text-title);
  }

  .lead {
    margin: 0 0 var(--space-4);
    color: var(--text-2);
  }

  .people {
    margin: 0 0 var(--space-4);
    padding: 0;
    list-style: none;
  }

  .people li {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
    padding-block: var(--space-2);
    border-block-end: 1px solid var(--border);
  }

  .people li.off .who {
    opacity: 0.6;
  }

  .who {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: 0;
  }

  small,
  .hint {
    color: var(--text-2);
    font-size: var(--text-small);
  }

  .hint {
    margin: var(--space-2) 0 0;
    max-width: 68ch;
  }

  .tag {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 2px var(--space-2);
    color: var(--accent-text);
    background: var(--accent-muted);
    border-radius: var(--radius-control);
    font-size: var(--text-small);
  }

  .tag.off {
    color: var(--danger-text);
    background: transparent;
  }

  .people button {
    height: var(--h-button-sm);
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding-inline: var(--space-2);
    color: var(--text-2);
    background: transparent;
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
    font-size: var(--text-small);
    cursor: pointer;
  }

  .people button:hover {
    color: var(--text);
    background: var(--surface-2);
  }

  .form {
    padding: var(--space-3);
    margin-block-end: var(--space-3);
    background: var(--surface-2);
    border-radius: var(--radius-card);
  }

  .label {
    margin: 0 0 var(--space-2);
    font-weight: 500;
  }

  .row {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: flex-end;
    margin-block-end: var(--space-2);
  }

  .row :global(.field) {
    flex: 1;
    min-width: 180px;
  }

  .check {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    margin-block-end: var(--space-3);
    font-size: var(--text-small);
  }

  .sk {
    height: 160px;
    background: var(--surface-1);
    border-radius: var(--radius-card);
  }

  .sk.small {
    height: 48px;
  }

  .theirs {
    flex-basis: 100%;
    padding: var(--space-2) var(--space-3);
    background: var(--surface-1);
    border-radius: var(--radius-group);
  }

  .theirs ul {
    margin: 0 0 var(--space-2);
    padding: 0;
    list-style: none;
  }

  .theirs li {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding-block: var(--space-1);
  }

  .pname {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .prole {
    color: var(--text-2);
    font-size: var(--text-small);
  }

  .theirs .x {
    width: var(--h-icon-sm);
    padding: 0;
    justify-content: center;
    border: 0;
  }

  select {
    height: var(--h-button-sm);
    padding-inline: var(--space-2);
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
  }
</style>
