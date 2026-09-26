<script lang="ts">
  import TipCard from '../../lib/ui/TipCard.svelte';
  import { Sparkles } from '@lucide/svelte';
  import { api, ApiError, waitForJob } from '../../lib/api/client';
  import type { MlStatus } from '../../lib/api/types';
  import { plural } from '../../lib/format';
  import { router } from '../../lib/state/router.svelte';
  import type { Workspace } from '../../lib/state/workspace.svelte';
  import Button from '../../lib/ui/Button.svelte';
  import Callout from '../../lib/ui/Callout.svelte';
  import Modal from '../../lib/ui/Modal.svelte';

  let { ws, onclose }: { ws: Workspace; onclose: () => void } = $props();

  let status = $state<MlStatus | null>(null);
  let problem = $state('');
  let model = $state('');
  let names = $state('');
  let confidence = $state(25);
  let scope = $state<'empty' | 'all'>('empty');
  let create = $state(true);
  let busy = $state(false);
  let progress = $state(0);
  let summary = $state('');
  let picker = $state<HTMLInputElement | undefined>();
  let uploading = $state(false);
  let uploadError = $state('');

  async function addModel(file: File): Promise<void> {
    uploading = true;
    uploadError = '';
    try {
      const added = await api.ml.addModel(file);
      status = await api.ml.status();
      model = added.name;
    } catch (err) {
      uploadError = err instanceof ApiError ? err.message : 'Could not add that model.';
    } finally {
      uploading = false;
      if (picker) picker.value = '';
    }
  }

  $effect(() => {
    api.ml
      .status()
      .then((s) => {
        status = s;
        model = s.models[0]?.name ?? '';
      })
      .catch((err: unknown) => {
        problem = err instanceof ApiError ? err.message : 'Could not check the models.';
      });
  });

  const chosen = $derived(status?.models.find((m) => m.name === model) ?? null);
  const needsNames = $derived(chosen !== null && chosen.classes === null);
  const ready = $derived(!!status?.enabled && status.installed && status.models.length > 0);

  async function run(): Promise<void> {
    busy = true;
    problem = '';
    summary = '';
    progress = 0;
    try {
      const typed = names.split('\n').map((n) => n.trim()).filter(Boolean);
      const started = await api.ml.prelabel(ws.projectId, {
        model,
        threshold: confidence / 100,
        only_unlabeled: scope === 'empty',
        create_missing_classes: create,
        class_names: needsNames ? typed : undefined,
      });
      const job = await waitForJob(started.id, (p) => (progress = p));
      if (job.status === 'failed') {
        problem = job.error ?? 'The model could not run.';
        return;
      }
      const result = job.result as {
        images: number;
        shapes: number;
        skipped_classes: string[];
        failed: string[];
        operation_id: string | null;
      };
      summary =
        result.shapes === 0
          ? 'The model did not find anything at this confidence. Try a lower one.'
          : `Drafted ${plural(result.shapes, 'box')} on ${plural(result.images, 'image')}. Look them over: they are drawn dashed until you edit them.`;
      if (result.skipped_classes.length > 0) {
        summary += ` Left out, because the project has no class for them: ${result.skipped_classes.join(', ')}.`;
      }
      if (result.failed.length > 0) summary += ` ${plural(result.failed.length, 'image')} could not be read.`;
      if (result.shapes > 0) {
        ws.announce(`Drafted ${plural(result.shapes, 'box')} with a model.`, result.operation_id);
        await ws.reloadCurrent();
      }
    } catch (err) {
      problem = err instanceof ApiError ? err.message : 'Could not start the model.';
    } finally {
      busy = false;
    }
  }
</script>

<Modal
  title="Pre-label with a model"
  description="Let your own detection model draft boxes, then correct them."
  width={520}
  {onclose}
>
  <TipCard id="dialog:prelabel" />
  <input
    bind:this={picker}
    type="file"
    accept=".onnx"
    hidden
    onchange={(e) => {
      const file = e.currentTarget.files?.[0];
      if (file) void addModel(file);
    }}
  />
  {#if status === null && !problem}
    <div class="sk" aria-busy="true"></div>
  {:else if status && !status.enabled}
    <Callout>
      <p class="line"><strong>Model pre-labeling is turned off.</strong></p>
      <p class="line">Turn it on under Settings, then Model help. It takes effect at once.</p>
      <Button onclick={() => router.navigate('/settings')}>Open Settings</Button>
    </Callout>
  {:else if status && !status.installed}
    <Callout>
      <p class="line"><strong>The model runtime is not installed.</strong></p>
      <p class="line">Katib needs one extra package to run models. Install it with
        <code>uv sync --extra ml</code> and restart Katib. The Docker image already has it.</p>
    </Callout>
  {:else if status && status.models.length === 0}
    <Callout>
      <p class="line"><strong>No models yet.</strong></p>
      <p class="line">
        Choose a YOLO detection model saved as <code>.onnx</code>. It is kept on the server, so you
        only do this once and everyone on this Katib can use it.
      </p>
      {#if uploadError}<p class="line bad">{uploadError}</p>{/if}
      <Button loading={uploading} onclick={() => picker?.click()}>
        {uploading ? 'Adding the model...' : 'Add a model'}
      </Button>
      {#if status.models_dir}
        <p class="line quiet">Or copy one into <code>{status.models_dir}</code> on the server.</p>
      {/if}
    </Callout>
  {:else if status}
    <label class="field">
      <span>Model</span>
      <select bind:value={model} disabled={busy}>
        {#each status.models as m (m.name)}<option value={m.name}>{m.name}</option>{/each}
      </select>
    </label>

    {#if chosen?.classes}
      <p class="hint">Finds: {chosen.classes.slice(0, 12).join(', ')}{chosen.classes.length > 12 ? `, and ${chosen.classes.length - 12} more` : ''}.</p>
    {:else if needsNames}
      <label class="field">
        <span>Class names, one per line, in the model's order</span>
        <textarea rows="4" bind:value={names} disabled={busy}></textarea>
      </label>
    {/if}

    <label class="field">
      <span>Minimum confidence: {confidence}%</span>
      <input type="range" min="5" max="95" step="5" bind:value={confidence} disabled={busy} />
    </label>

    <fieldset class="scope">
      <legend>Which images?</legend>
      <label><input type="radio" value="empty" bind:group={scope} disabled={busy} />Images without any shapes</label>
      <label><input type="radio" value="all" bind:group={scope} disabled={busy} />All images. Existing shapes stay.</label>
    </fieldset>

    <label class="check">
      <input type="checkbox" bind:checked={create} disabled={busy} />
      Create a class for each thing the model finds that the project does not have yet
    </label>

    {#if busy}
      <div class="bar" role="progressbar" aria-label="Pre-label progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round(progress * 100)}>
        <span style:width="{Math.round(progress * 100)}%"></span>
      </div>
    {/if}
  {/if}

  {#if problem}<Callout tone="danger">{problem}</Callout>{/if}
  {#if summary}<Callout>{summary}</Callout>{/if}

  {#snippet footer()}
    <Button onclick={onclose}>Close</Button>
    {#if ready}
      <Button variant="primary" loading={busy} disabled={!model || (needsNames && !names.trim())} onclick={run}>
        <Sparkles size={16} />Run the model
      </Button>
    {/if}
  {/snippet}
</Modal>

<style>
  .field,
  .scope,
  .check {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    margin-block-end: var(--space-3);
  }

  .field span,
  legend {
    font-weight: 500;
  }

  select,
  textarea {
    padding: var(--space-2);
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
    font: inherit;
  }

  .scope {
    padding: 0;
    border: 0;
  }

  .scope label,
  .check {
    flex-direction: row;
    align-items: flex-start;
    gap: var(--space-2);
  }

  .hint {
    margin: 0 0 var(--space-3);
    color: var(--text-2);
    font-size: var(--text-small);
  }

  .line {
    margin: 0 0 var(--space-1);
  }

  .line.bad {
    color: var(--danger-text, var(--warning-text));
  }

  .line.quiet {
    margin-block-start: var(--space-2);
    font-size: var(--text-small);
    color: var(--text-2);
  }

  .bar {
    height: 4px;
    margin-block: var(--space-3);
    background: var(--border);
    border-radius: 2px;
    overflow: hidden;
  }

  .bar span {
    display: block;
    height: 100%;
    background: var(--accent);
  }

  .sk {
    height: 120px;
    background: var(--surface-1);
    border-radius: var(--radius-card);
  }
</style>
