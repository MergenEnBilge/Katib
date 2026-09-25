<script lang="ts">
  import { Download } from '@lucide/svelte';
  import { api, ApiError, waitForJob } from '../../lib/api/client';
  import { formatBytes } from '../../lib/format';
  import Button from '../../lib/ui/Button.svelte';
  import Callout from '../../lib/ui/Callout.svelte';

  let { database }: { database: string } = $props();

  let busy = $state(false);
  let progress = $state(0);
  let error = $state('');
  let file = $state<{ url: string; size: number } | null>(null);

  async function run(): Promise<void> {
    busy = true;
    error = '';
    file = null;
    progress = 0;
    try {
      const started = await api.settings.backup();
      const job = await waitForJob(started.id, (p) => (progress = p));
      if (job.status === 'failed') {
        error = job.error ?? 'The backup failed.';
        return;
      }
      const result = job.result as { bytes: number };
      file = { url: api.jobs.downloadUrl(job.id), size: result.bytes };
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not make a backup.';
    } finally {
      busy = false;
    }
  }
</script>

<h2>Backup</h2>
<p class="lead">
  A backup is one zip file with your projects, labels, settings and the pictures you uploaded. Keep a
  copy somewhere else, such as an external drive or cloud storage.
</p>

{#if database === 'SQLite'}
  <div class="what">
    <h3>What is in it</h3>
    <ul>
      <li>All projects, classes, labels, comments and team members.</li>
      <li>Pictures you uploaded from your device.</li>
      <li>Your saved settings and the undo history.</li>
    </ul>
    <h3>What is not</h3>
    <ul>
      <li>Pictures in folders you connected. They are your own files and Katib never copies them, so back them up as you already do.</li>
      <li>Thumbnails, which Katib makes again when needed.</li>
    </ul>
  </div>

  {#if error}<Callout tone="danger">{error}</Callout>{/if}
  {#if file}
    <Callout>
      Your backup is ready ({formatBytes(file.size)}).
      {#snippet action()}
        <a class="download" href={file?.url} download><Download size={16} />Download backup</a>
      {/snippet}
    </Callout>
  {/if}
  <div class="actions">
    <Button variant="primary" disabled={busy} onclick={run}>
      {busy ? `Backing up ${Math.round(progress * 100)}%` : 'Make a backup'}
    </Button>
  </div>

  <h3>Getting it back</h3>
  <p>
    Close Katib, then run <code class="mono">katib restore your-backup.zip</code> on the computer that
    runs it. Katib refuses to overwrite a database that is already there unless you add
    <code class="mono">--replace</code>, and even then it keeps the old one beside it.
  </p>
{:else}
  <Callout>
    This server uses {database}. Back the database up with your database's own tools, such as
    <span class="mono">pg_dump</span>, and copy the data folder for uploaded pictures.
  </Callout>
{/if}

<style>
  h2 {
    margin: 0 0 var(--space-1);
    font-size: var(--text-title);
  }

  h3 {
    margin: var(--space-4) 0 var(--space-1);
    font-size: var(--text-heading);
  }

  .lead {
    margin: 0;
    color: var(--text-2);
    max-width: 68ch;
  }

  ul {
    margin: 0;
    padding-inline-start: var(--space-4);
    color: var(--text-2);
  }

  p {
    max-width: 68ch;
    color: var(--text-2);
  }

  .actions {
    margin-block: var(--space-4);
  }

  code {
    padding: 1px 6px;
    background: var(--surface-2);
    border-radius: var(--radius-chip);
  }

  .download {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    height: var(--h-button);
    padding-inline: var(--space-3);
    color: var(--on-accent);
    font-weight: 500;
    text-decoration: none;
    background: var(--accent);
    border-radius: var(--radius-control);
    white-space: nowrap;
  }
</style>
