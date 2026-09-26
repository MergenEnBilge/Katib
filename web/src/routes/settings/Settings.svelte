<script lang="ts">
  import { api, ApiError } from '../../lib/api/client';
  import type { AppSettings } from '../../lib/api/types';
  import { plural } from '../../lib/format';
  import { session } from '../../lib/state/session.svelte';
  import { toasts } from '../../lib/state/toast.svelte';
  import Button from '../../lib/ui/Button.svelte';
  import Callout from '../../lib/ui/Callout.svelte';
  import AboutPanel from './AboutPanel.svelte';
  import AppearancePanel from './AppearancePanel.svelte';
  import BackupPanel from './BackupPanel.svelte';
  import ModePicker from './ModePicker.svelte';
  import PeoplePanel from './PeoplePanel.svelte';
  import SettingRow from './SettingRow.svelte';
  import SegmentPanel from './SegmentPanel.svelte';
  import SharePanel from './SharePanel.svelte';
  import TipCard from '../../lib/ui/TipCard.svelte';

  let data = $state<AppSettings | null>(null);
  let error = $state('');
  let denied = $state(false);
  let draft = $state<Record<string, unknown>>({});
  let tab = $state('sharing');
  let busy = $state(false);
  let restarting = $state(false);
  let dbResult = $state<{ ok: boolean; message: string } | null>(null);

  const tabs = $derived([
    ...(data?.groups ?? []).map((g) => ({ id: g.id, label: g.label })),
    ...(session.mode === 'local' ? [{ id: 'people', label: 'People' }] : []),
    { id: 'backup', label: 'Backup' },
    { id: 'appearance', label: 'Appearance' },
    { id: 'about', label: 'About' },
  ]);
  const group = $derived(data?.groups.find((g) => g.id === tab));
  const fields = $derived((data?.fields ?? []).filter((f) => f.group === tab));

  const changed = $derived(
    (data?.fields ?? []).filter((f) => f.key in draft && JSON.stringify(draft[f.key]) !== JSON.stringify(f.value)),
  );

  async function load(): Promise<void> {
    error = '';
    try {
      data = await api.settings.get();
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) denied = true;
      else error = err instanceof ApiError ? err.message : 'Could not load the settings.';
    }
  }

  $effect(() => {
    void load();
  });

  function shown(key: string, fallback: unknown): unknown {
    return key in draft ? draft[key] : fallback;
  }

  async function save(): Promise<void> {
    busy = true;
    error = '';
    try {
      const values: Record<string, unknown> = {};
      for (const f of changed) values[f.key] = draft[f.key];
      data = await api.settings.save(values);
      draft = {};
      toasts.show(data.info.restart_pending ? 'Saved. Restart Katib to apply some of these.' : 'Saved.');
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not save the settings.';
    } finally {
      busy = false;
    }
  }

  async function testDatabase(): Promise<void> {
    dbResult = null;
    try {
      dbResult = await api.settings.testDatabase(String(draft['database.url'] ?? ''));
    } catch (err) {
      dbResult = { ok: false, message: err instanceof ApiError ? err.message : 'Could not test.' };
    }
  }

  /** Where Katib will answer after the restart. A new port means a new address. */
  function afterRestartUrl(): string {
    const port = data?.fields.find((f) => f.key === 'server.port');
    const next = port && typeof port.value === 'number' ? port.value : Number(location.port || 80);
    return `${location.protocol}//${location.hostname}:${next}${location.pathname}`;
  }

  async function restart(): Promise<void> {
    const target = afterRestartUrl();
    try {
      await api.settings.restart();
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not restart.';
      return;
    }
    restarting = true;
    // Wait for the new copy to answer, then go to it. `no-cors` is enough to tell it is up.
    const health = new URL('/api/v1/health', target).toString();
    for (let i = 0; i < 60; i++) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      try {
        await fetch(health, { mode: 'no-cors', cache: 'no-store' });
        location.assign(target);
        return;
      } catch {
        // Not back yet.
      }
    }
    restarting = false;
    error = 'Katib did not come back. Start it again by hand.';
  }
</script>

<header class="page-header">
  <h1>Settings</h1>
</header>

{#if denied}
  <Callout>Only an administrator can change settings on this server.</Callout>
{:else if error && !data}
  <Callout tone="danger">
    {error}
    {#snippet action()}<Button onclick={load}>Try again</Button>{/snippet}
  </Callout>
{:else if !data}
  <div class="loading" aria-busy="true"></div>
{:else}
  {#if data.info.restart_pending}
    <div class="restart">
      <Callout>
        Some saved settings apply after Katib restarts.
        {#snippet action()}
          {#if data?.info.can_restart}
            <Button variant="primary" loading={restarting} onclick={restart}>{restarting ? 'Restarting...' : 'Restart Katib now'}</Button>
          {:else}
            <span class="quiet">Close Katib and open it again.</span>
          {/if}
        {/snippet}
      </Callout>
    </div>
  {/if}

  <div class="layout">
    <nav class="tabs" aria-label="Settings sections" data-tour="settings-tabs">
      {#each tabs as item (item.id)}
        <button type="button" class:active={tab === item.id} aria-current={tab === item.id ? 'page' : undefined} onclick={() => (tab = item.id)}>
          {item.label}
        </button>
      {/each}
    </nav>

    <section class="panel" aria-labelledby="section-title" data-tour="settings-body">
      {#if group}
        <h2 id="section-title">{group.label}</h2>
        <p class="lead">{group.help}</p>
        <TipCard id="settings:{tab}" />
        {#if tab === 'sharing'}
          <ModePicker
            current={(key) => shown(key, data?.fields.find((f) => f.key === key)?.value)}
            lockedBy={(key) => {
              const field = data?.fields.find((f) => f.key === key);
              return field?.source === 'environment' ? (field.env_name ?? null) : null;
            }}
            onpick={(values) => (draft = { ...draft, ...values })}
          />
        {/if}
        {#each fields as field (field.key)}
          <SettingRow
            {field}
            value={shown(field.key, field.value)}
            onchange={(v) => (draft[field.key] = v)}
          >
            {#snippet extra()}
              {#if field.key === 'database.url'}
                <div class="test">
                  <Button onclick={testDatabase}>Test connection</Button>
                  {#if dbResult}<span class:bad={!dbResult.ok} role="status">{dbResult.message}</span>{/if}
                </div>
              {/if}
            {/snippet}
          </SettingRow>
        {/each}

        {#if tab === 'sharing'}<SharePanel />{/if}
        {#if tab === 'model'}<SegmentPanel />{/if}

        {#if error}<Callout tone="danger">{error}</Callout>{/if}
        <div class="save" data-tour="settings-save">
          <span class="count">{changed.length ? plural(changed.length, 'change') + ' not saved' : 'No changes'}</span>
          <Button disabled={changed.length === 0 || busy} onclick={() => (draft = {})}>Discard</Button>
          <Button variant="primary" loading={busy} disabled={changed.length === 0} onclick={save}>{busy ? 'Saving...' : 'Save changes'}</Button>
        </div>
      {:else if tab === 'people'}
        <PeoplePanel />
      {:else if tab === 'backup'}
        <BackupPanel database={data.info.database} />
      {:else if tab === 'appearance'}
        <AppearancePanel />
      {:else}
        <AboutPanel info={data.info} shared={session.mode === 'local'} />
      {/if}
    </section>
  </div>
{/if}

<style>
  .page-header {
    margin-block-end: var(--space-4);
  }

  .restart {
    margin-block-end: var(--space-4);
  }

  .quiet {
    color: var(--text-2);
  }

  .layout {
    display: grid;
    grid-template-columns: 180px minmax(0, 1fr);
    gap: var(--space-6);
    align-items: start;
    max-width: 980px;
  }

  .tabs {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .tabs button {
    height: var(--h-button);
    padding-inline: var(--space-3);
    text-align: start;
    color: var(--text-2);
    background: none;
    border: 0;
    border-radius: var(--radius-control);
    cursor: pointer;
  }

  .tabs button.active {
    color: var(--text);
    font-weight: 500;
    background: var(--accent-muted);
  }

  .tabs button:hover:not(.active) {
    background: var(--surface-2);
  }

  h2 {
    margin: 0 0 var(--space-1);
    font-size: var(--text-title);
  }

  .lead {
    margin: 0;
    color: var(--text-2);
  }

  .test {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    font-size: var(--text-small);
  }

  .test .bad {
    color: var(--danger-text);
  }

  .save {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: var(--space-2);
    position: sticky;
    bottom: 0;
    z-index: 2;
    border-block-start: 1px solid var(--border);
    padding-block: var(--space-3);
    background: var(--bg);
  }

  .count {
    margin-inline-end: auto;
    font-size: var(--text-small);
    color: var(--text-2);
  }

  .loading {
    height: 240px;
    background: var(--surface-1);
    border-radius: var(--radius-card);
  }

  @media (max-width: 699px) {
    .layout {
      grid-template-columns: 1fr;
      gap: var(--space-3);
    }

    .tabs {
      flex-direction: row;
      flex-wrap: wrap;
    }

    /* On a small screen the bar sits after the last setting, where it cannot cover anything. */
    .save {
      position: static;
    }
  }
</style>
