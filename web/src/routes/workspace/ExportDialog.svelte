<script lang="ts">
  import { Download } from '@lucide/svelte';
  import { api, ApiError, waitForJob } from '../../lib/api/client';
  import type { FormatInfo } from '../../lib/api/types';
  import { plural } from '../../lib/format';
  import type { Workspace } from '../../lib/state/workspace.svelte';
  import Button from '../../lib/ui/Button.svelte';
  import Callout from '../../lib/ui/Callout.svelte';
  import Modal from '../../lib/ui/Modal.svelte';

  let { ws, onclose }: { ws: Workspace; onclose: () => void } = $props();

  let formats = $state<FormatInfo[]>([]);
  let format = $state('yolo-detect');
  let which = $state<'all' | 'done' | 'notdone'>('all');
  let copyImages = $state(false);
  let splitOn = $state(false);
  let train = $state(80);
  let val = $state(10);
  let test = $state(10);
  let seed = $state(0);
  let stratify = $state(true);
  let orderChanged = $state(false);
  let busy = $state(false);
  let error = $state('');
  let downloadUrl = $state('');
  let result = $state<{ images: number; shapes: number; notes: { subject: string; reason: string }[] } | null>(null);

  $effect(() => {
    api.exportInfo(ws.projectId).then((i) => (orderChanged = i.order_changed)).catch(() => undefined);
  });

  $effect(() => {
    api.formats().then((f) => (formats = f)).catch(() => undefined);
  });

  const statuses = $derived(
    which === 'done' ? ['done'] : which === 'notdone' ? ['todo', 'in_progress'] : undefined,
  );

  async function run(): Promise<void> {
    busy = true;
    error = '';
    downloadUrl = '';
    result = null;
    try {
      await ws.flushNow();
      const split = splitOn ? { train: train / 100, val: val / 100, test: test / 100, seed, stratify } : undefined;
      const started = await api.jobs.exportDataset(ws.projectId, format, statuses, copyImages, split);
      const job = await waitForJob(started.id);
      if (job.status === 'failed') {
        error = job.error ?? 'The export failed.';
        return;
      }
      result = job.result as typeof result;
      downloadUrl = api.jobs.downloadUrl(job.id);
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not export.';
    } finally {
      busy = false;
    }
  }
</script>

<Modal
  title="Export"
  description="Write your labels to a zip file in the format your training code expects."
  {onclose}
>
  <div class="form">
    <label class="field">
      <span>Format</span>
      <select bind:value={format} disabled={busy}>
        {#each formats as f (f.id)}<option value={f.id}>{f.label}</option>{/each}
      </select>
    </label>

    <fieldset disabled={busy}>
      <legend>Images</legend>
      <label><input type="radio" bind:group={which} value="all" /> All images</label>
      <label><input type="radio" bind:group={which} value="done" /> Done only</label>
      <label><input type="radio" bind:group={which} value="notdone" /> Not done yet</label>
    </fieldset>

    <label class="check"><input type="checkbox" bind:checked={copyImages} disabled={busy} /> Include the image files</label>

    <label class="check"><input type="checkbox" bind:checked={splitOn} disabled={busy} /> Split into train, validation and test</label>
    {#if splitOn}
      <div class="split">
        <label>Train %<input type="number" min="0" max="100" bind:value={train} /></label>
        <label>Validation %<input type="number" min="0" max="100" bind:value={val} /></label>
        <label>Test %<input type="number" min="0" max="100" bind:value={test} /></label>
        <label>Seed<input type="number" bind:value={seed} /></label>
        <label class="check wide"><input type="checkbox" bind:checked={stratify} /> Keep rare classes in every split</label>
      </div>
    {/if}

    <div class="order">
      <p class="label">Class order</p>
      <p class="mono">{ws.classes.map((c, i) => `${i} ${c.name}`).join(', ') || 'No classes yet'}</p>
      <p class="note">Formats that number classes use this order. Reordering classes changes the numbers.</p>
      {#if orderChanged}
        <Callout>The class order changed since your last export, so class numbers no longer match models trained on it.</Callout>
      {/if}
    </div>
  </div>

  {#if error}<Callout tone="danger">{error}</Callout>{/if}
  {#if result}
    <Callout>
      <p class="line">{plural(result.shapes, 'shape')} in {plural(result.images, 'image')}.</p>
      {#if result.notes.length}
        <details class="notes">
          <summary>{plural(result.notes.length, 'note')}</summary>
          <ul>{#each result.notes as n, i (i)}<li><span class="mono">{n.subject}</span> {n.reason}</li>{/each}</ul>
        </details>
      {/if}
      {#snippet action()}
        <a class="download" href={downloadUrl} download><Download size={16} />Download zip</a>
      {/snippet}
    </Callout>
  {/if}

  {#snippet footer()}
    <Button onclick={onclose}>Close</Button>
    <Button variant="primary" disabled={busy || ws.classes.length === 0} onclick={run}>
      {busy ? 'Exporting...' : 'Export'}
    </Button>
  {/snippet}
</Modal>

<style>
  .form {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    margin-block-end: var(--space-3);
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    font-weight: 500;
  }

  select {
    height: var(--h-input);
    padding-inline: var(--space-2);
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
  }

  fieldset {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    margin: 0;
    padding: 0;
    border: 0;
  }

  legend {
    padding: 0;
    margin-block-end: var(--space-1);
    font-weight: 500;
  }

  .split {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: var(--space-2);
    font-size: var(--text-small);
    color: var(--text-2);
  }

  .split label {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .split input[type='number'] {
    height: var(--h-button-sm);
    padding-inline: var(--space-2);
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
  }

  .split .wide {
    grid-column: 1 / -1;
    flex-direction: row;
  }

  .check {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .order p {
    margin: 0;
  }

  .label {
    font-weight: 500;
  }

  .note {
    margin-block-start: var(--space-1);
    font-size: var(--text-small);
    color: var(--text-2);
  }

  .line {
    margin: 0;
  }

  .notes {
    margin-block-start: var(--space-2);
    font-size: var(--text-small);
    color: var(--text-2);
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

  .download:hover {
    background: var(--accent-hover);
  }
</style>
