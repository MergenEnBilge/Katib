<script lang="ts">
  import TipCard from '../../lib/ui/TipCard.svelte';
  import { Download } from '@lucide/svelte';
  import { api, ApiError, waitForJob } from '../../lib/api/client';
  import type { FormatInfo } from '../../lib/api/types';
  import { plural } from '../../lib/format';
  import { onboarding } from '../../lib/state/onboarding.svelte';
  import type { Workspace } from '../../lib/state/workspace.svelte';
  import Button from '../../lib/ui/Button.svelte';
  import TextField from '../../lib/ui/TextField.svelte';
  import Callout from '../../lib/ui/Callout.svelte';
  import Modal from '../../lib/ui/Modal.svelte';

  let {
    ws,
    onclose,
    onclasses,
  }: { ws: Workspace; onclose: () => void; onclasses: () => void } = $props();

  let formats = $state<FormatInfo[]>([]);
  let format = $state('yolo-detect');

  /** Where each kind of project starts: the format most people want, not the first listed. */
  const USUAL: Record<string, string> = { image: 'yolo-detect', text: 'jsonl-spans' };
  let which = $state<'all' | 'done' | 'notdone'>('all');
  let copyImages = $state(false);
  const isText = $derived(ws.medium === 'text');
  let saveHere = $state(false);
  let destination = $state('');
  let moveFiles = $state(false);
  let moveConfirmation = $state('');
  const moveReady = $derived(!saveHere || !moveFiles || moveConfirmation.trim() === 'MOVE');
  const folderReady = $derived(!saveHere || destination.trim() !== '');

  /** Forget the move and its confirmation when the folder they belong to is turned off. */
  function folderToggled(): void {
    if (saveHere) return;
    moveFiles = false;
    moveConfirmation = '';
  }
  let splitMode = $state<'saved' | 'new' | 'none'>('none');
  let saved = $state<{ train: number; val: number; test: number; none: number } | null>(null);
  let train = $state(80);
  let val = $state(10);
  let test = $state(10);
  let seed = $state(0);
  let stratify = $state(true);
  const shares = $derived(train + val + test);
  /** What the three shares become once they are scaled to add up, so nobody has to guess. */
  const scaled = $derived({
    train: shares ? Math.round((train / shares) * 100) : 0,
    val: shares ? Math.round((val / shares) * 100) : 0,
    test: shares ? Math.round((test / shares) * 100) : 0,
  });
  let orderChanged = $state(false);
  let busy = $state(false);
  let error = $state('');
  let downloadUrl = $state('');
  let example = $state('/data/exports/street');
  let result = $state<{ images: number; shapes: number; folder?: string | null; notes: { subject: string; reason: string }[] } | null>(null);

  $effect(() => {
    api.exportInfo(ws.projectId).then((i) => (orderChanged = i.order_changed)).catch(() => undefined);
    // A real folder on the server, so the box shows the right shape of path for it.
    api.folders
      .browse()
      .then((l) => (example = l.example ? `${l.example}/export` : example))
      .catch(() => undefined);
  });

  $effect(() => {
    api.splits
      .get(ws.projectId)
      .then((s) => {
        const [train, val, test, none] = ['train', 'val', 'test', 'none'].map((k) => s.counts[k] ?? 0) as [number, number, number, number];
        if (train + val + test > 0) {
          saved = { train, val, test, none };
          splitMode = 'saved';
        }
      })
      .catch(() => undefined);
  });

  $effect(() => {
    api
      .formats()
      // Text and pictures are different worlds, so a project is only offered its own formats.
      .then((f) => {
        formats = f.filter((x) => x.can_export !== false && x.medium === ws.medium);
        // The starting format suits a picture project. A text project has its own, so move
        // to the one most people want rather than leaving a format it cannot export here.
        if (!formats.some((x) => x.id === format)) {
          const usual = USUAL[ws.medium];
          format = formats.find((x) => x.id === usual)?.id ?? formats[0]?.id ?? '';
        }
      })
      .catch((err: unknown) => {
        error = err instanceof ApiError ? err.message : 'Could not load the list of formats.';
      });
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
      const split =
        splitMode === 'new'
          ? { train: train / 100, val: val / 100, test: test / 100, seed, stratify }
          : undefined;
      const started = await api.jobs.exportDataset(
        ws.projectId,
        format,
        statuses,
        copyImages,
        split,
        splitMode === 'saved',
        saveHere && destination.trim() ? destination.trim() : undefined,
        saveHere && moveFiles,
      );
      const job = await waitForJob(started.id);
      if (job.status === 'failed') {
        error = job.error ?? 'The export failed.';
        return;
      }
      result = job.result as typeof result;
      onboarding.mark('export');
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
  <TipCard id="dialog:export" />
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

    {#if isText}
      <p class="note">The words of each document are written into the file, so it stands alone.</p>
    {:else}
      <label class="check"><input type="checkbox" bind:checked={copyImages} disabled={busy} /> Include the image files</label>
    {/if}

    <label class="check"><input type="checkbox" bind:checked={saveHere} onchange={folderToggled} disabled={busy} /> Save into a folder on the Katib computer instead of a zip</label>
    {#if saveHere}
      <TextField label="Folder to write into" placeholder={example} bind:value={destination} hint="Must be empty or new. Only administrators can save to a folder on the server." />
      {#if !folderReady}
        <p class="note">Name the folder to write into, or turn this off to download a zip instead.</p>
      {/if}
      <label class="check"><input type="checkbox" bind:checked={moveFiles} disabled={busy} /> Move the pictures there instead of copying them</label>
      {#if moveFiles}
        <Callout>
          The pictures leave their current folders and go into the export folder. Label files refer to them by name. Katib cannot undo this for you. Type MOVE to confirm.
        </Callout>
        <TextField label="Type MOVE to confirm" bind:value={moveConfirmation} />
      {/if}
    {/if}

    <fieldset disabled={busy}>
      <legend>Train, validation and test</legend>
      {#if saved}
        <label>
          <input type="radio" bind:group={splitMode} value="saved" />
          Use the split saved on my images
          <span class="hint">{saved.train} train, {saved.val} validation, {saved.test} test{saved.none ? `. ${saved.none} with no split go to train` : ''}</span>
        </label>
      {/if}
      <label><input type="radio" bind:group={splitMode} value="new" /> Make a new split for this export only</label>
      <label><input type="radio" bind:group={splitMode} value="none" /> Do not split</label>
    </fieldset>
    {#if splitMode === 'new'}
      <div class="split">
        <label>Train %<input type="number" min="0" max="100" bind:value={train} /></label>
        <label>Validation %<input type="number" min="0" max="100" bind:value={val} /></label>
        <label>Test %<input type="number" min="0" max="100" bind:value={test} /></label>
        <label>Seed<input type="number" bind:value={seed} /></label>
        <label class="check wide"><input type="checkbox" bind:checked={stratify} /> Keep rare classes in every split</label>
      </div>
      {#if shares !== 100}
        <p class="note">
          Those add up to {shares}%, so they will be scaled to fit: about {scaled.train}% train,
          {scaled.val}% validation and {scaled.test}% test. Make them add up to 100 to say exactly.
        </p>
      {/if}
    {/if}

    <div class="order">
      <p class="label">Class order</p>
      <p class="mono">{ws.classes.map((c, i) => `${i} ${c.name}`).join(', ') || 'No classes yet'}</p>
      <p class="note">Formats that number classes use this order. Change it in the class manager, and the numbers change with it.</p>
      {#if orderChanged}
        <Callout>The class order changed since your last export, so class numbers no longer match models trained on it.</Callout>
      {/if}
    </div>
  </div>

  {#if ws.classes.length === 0}
    <Callout>
      Add at least one class before exporting. A label file names the classes, so there is nothing
      to write until this project has some.
      {#snippet action()}
        <Button onclick={onclasses}>Add a class</Button>
      {/snippet}
    </Callout>
  {/if}
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
        {#if result?.folder}
          <p class="line">Saved to <span class="mono">{result?.folder}</span></p>
        {:else}
          <a class="download" href={downloadUrl} download><Download size={16} />Download zip</a>
        {/if}
      {/snippet}
    </Callout>
  {/if}

  {#snippet footer()}
    <Button onclick={onclose}>Close</Button>
    <Button
      variant="primary"
      loading={busy}
      disabled={ws.classes.length === 0 || !format || !moveReady || !folderReady}
      onclick={run}
    >
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

  .hint {
    display: block;
    margin-inline-start: 22px;
    font-size: var(--text-small);
    color: var(--text-2);
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
