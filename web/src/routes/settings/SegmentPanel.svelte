<script lang="ts">
  // Click to select needs a Segment Anything model, which comes as two files rather than one: the
  // encoder that looks at a picture and the decoder that turns a click into a mask. Katib cannot
  // tell them apart by looking, so it asks which is which and then keeps them under its own names.
  import { api, ApiError, waitForJob } from '../../lib/api/client';
  import type { MlStatus } from '../../lib/api/types';
  import { formatBytes } from '../../lib/format';
  import Button from '../../lib/ui/Button.svelte';
  import Callout from '../../lib/ui/Callout.svelte';

  let status = $state<MlStatus | null>(null);
  let error = $state('');
  let uploading = $state('');
  let downloading = $state('');
  let progress = $state(0);
  let encoderPicker = $state<HTMLInputElement | null>(null);
  let decoderPicker = $state<HTMLInputElement | null>(null);

  function load(): void {
    api.ml
      .status()
      .then((s) => (status = s))
      .catch((err: unknown) => {
        error = err instanceof ApiError ? err.message : 'Could not check the models.';
      });
  }

  $effect(load);

  async function upload(file: File, kind: 'sam-encoder' | 'sam-decoder'): Promise<void> {
    uploading = kind;
    error = '';
    try {
      await api.ml.addModel(file, kind);
      load();
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not add that file.';
    } finally {
      uploading = '';
    }
  }

  async function download(modelId: string): Promise<void> {
    downloading = modelId;
    progress = 0;
    error = '';
    try {
      const started = await api.ml.download(modelId);
      const job = await waitForJob(started.id, (p) => (progress = p));
      if (job.status === 'failed') {
        error = job.error ?? 'Could not download that model.';
        return;
      }
      load();
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not download that model.';
    } finally {
      downloading = '';
    }
  }
</script>

<section class="segment" aria-labelledby="segment-title">
  <h3 id="segment-title">Click to select</h3>
  <p class="quiet">
    With a Segment Anything model on this server, clicking an object outlines it. The tool appears
    in the toolbar of any project that uses polygons.
  </p>

  <input
    bind:this={encoderPicker}
    type="file"
    accept=".onnx"
    hidden
    onchange={(e) => {
      const file = e.currentTarget.files?.[0];
      if (file) void upload(file, 'sam-encoder');
    }}
  />
  <input
    bind:this={decoderPicker}
    type="file"
    accept=".onnx"
    hidden
    onchange={(e) => {
      const file = e.currentTarget.files?.[0];
      if (file) void upload(file, 'sam-decoder');
    }}
  />

  {#if error}<Callout tone="danger">{error}</Callout>{/if}

  {#if status?.can_segment}
    <Callout>A model is loaded. Press <strong>S</strong> in a project and click an object.</Callout>
  {/if}

  {#if status?.downloads?.length}
    <p class="label">Download a model</p>
    <p class="quiet">
      The one thing Katib fetches from the internet on its own, and only when asked here by name.
      Each one is checked against the exact bytes it had when it was added below.
    </p>
    <ul class="downloads">
      {#each status.downloads as d (d.id)}
        <li>
          <span class="who">
            <strong>{d.label}</strong>
            <small>{d.help} {formatBytes(d.bytes)} to download.</small>
          </span>
          {#if d.installed}
            <span class="installed">Installed</span>
          {:else}
            <Button
              loading={downloading === d.id}
              onclick={() => download(d.id)}
            >
              {downloading === d.id ? `Downloading ${Math.round(progress * 100)}%` : 'Download'}
            </Button>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}

  <p class="label">Or add your own files</p>
  <div class="halves">
    <div>
      <p class="label">Image encoder</p>
      <p class="quiet">The half that looks at the picture. Usually the larger file.</p>
      <Button loading={uploading === 'sam-encoder'} onclick={() => encoderPicker?.click()}>
        Choose a file
      </Button>
    </div>
    <div>
      <p class="label">Mask decoder</p>
      <p class="quiet">The half that turns a click into an outline. Usually a few megabytes.</p>
      <Button loading={uploading === 'sam-decoder'} onclick={() => decoderPicker?.click()}>
        Choose a file
      </Button>
    </div>
  </div>

  <p class="quiet">
    Both must be ONNX exports of the same model. Uploading either half again replaces it.
  </p>
</section>

<style>
  .segment {
    margin-block-start: var(--space-6);
  }

  h3 {
    margin: 0 0 var(--space-2);
    font-size: var(--text-heading);
  }

  .quiet {
    margin: 0 0 var(--space-2);
    max-width: 68ch;
    color: var(--text-2);
  }

  .halves {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-4);
    margin-block: var(--space-3);
  }

  .halves > div {
    flex: 1;
    min-width: 240px;
    padding: var(--space-3);
    background: var(--surface-2);
    border-radius: var(--radius-card);
  }

  .label {
    margin: 0 0 var(--space-1);
    font-weight: 500;
  }

  .downloads {
    margin: 0 0 var(--space-4);
    padding: 0;
    list-style: none;
    border: 1px solid var(--border);
    border-radius: var(--radius-control);
  }

  .downloads li {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-2) var(--space-3);
    border-block-end: 1px solid var(--border);
  }

  .downloads li:last-child {
    border-block-end: 0;
  }

  .who {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: 0;
  }

  .installed {
    color: var(--text-2);
    font-size: var(--text-small);
  }
</style>
