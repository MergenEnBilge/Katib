<script lang="ts">
  import TipCard from '../../lib/ui/TipCard.svelte';
  import { FolderOpen, RefreshCw, X } from '@lucide/svelte';
  import { api, ApiError, waitForJob } from '../../lib/api/client';
  import type { ConnectedFolder, FormatInfo, Job } from '../../lib/api/types';
  import { plural } from '../../lib/format';
  import Button from '../../lib/ui/Button.svelte';
  import Callout from '../../lib/ui/Callout.svelte';
  import Modal from '../../lib/ui/Modal.svelte';
  import TextField from '../../lib/ui/TextField.svelte';
  import FolderPicker from './FolderPicker.svelte';

  let {
    projectId,
    initialTab = 'images',
    ondone,
    onclose,
  }: {
    projectId: string;
    initialTab?: 'images' | 'labels';
    ondone: () => void;
    onclose: () => void;
  } = $props();

  interface Note {
    subject: string;
    reason: string;
  }

  // svelte-ignore state_referenced_locally
  let tab = $state<'images' | 'labels'>(initialTab);
  let typedFolder = $state('');
  let connected = $state<ConnectedFolder[]>([]);
  let picking = $state(false);
  let labelPath = $state('');
  let format = $state('');
  let formats = $state<FormatInfo[]>([]);
  let busy = $state(false);
  let progress = $state(0);
  let error = $state('');
  let summary = $state<string[]>([]);
  let notes = $state<Note[]>([]);
  let files: FileList | null = $state(null);
  let changed = false;

  $effect(() => {
    api.formats().then((f) => (formats = f)).catch(() => undefined);
    void loadConnected();
  });

  async function loadConnected(): Promise<void> {
    try {
      connected = await api.folders.connected(projectId);
    } catch {
      connected = [];
    }
  }

  function fail(err: unknown, fallback: string): void {
    error = err instanceof ApiError ? err.message : fallback;
  }

  function startOver(): void {
    busy = true;
    error = '';
    summary = [];
    notes = [];
    progress = 0;
  }

  /** Follow an image import until it ends, then show what happened. */
  async function finishImport(job: Job): Promise<void> {
    const done = await waitForJob(job.id, (p) => (progress = p));
    if (done.status === 'failed') {
      error = done.error ?? 'The import failed.';
      return;
    }
    const result = done.result as { added: number; skipped_count: number; skipped: { name: string; reason: string }[] };
    changed = true;
    summary = [
      `${plural(result.added, 'image')} added.`,
      result.skipped_count ? `${plural(result.skipped_count, 'file')} skipped.` : '',
    ].filter(Boolean);
    notes = result.skipped.map((s) => ({ subject: s.name, reason: s.reason }));
  }

  async function connectFolder(path: string): Promise<void> {
    picking = false;
    startOver();
    try {
      const made = await api.folders.connect(projectId, path);
      await loadConnected();
      await finishImport(made.job);
    } catch (err) {
      fail(err, 'Could not connect that folder.');
    } finally {
      busy = false;
    }
  }

  async function rescan(folder: ConnectedFolder): Promise<void> {
    startOver();
    try {
      await finishImport(await api.folders.rescan(projectId, folder.id));
    } catch (err) {
      fail(err, 'Could not scan that folder.');
    } finally {
      busy = false;
    }
  }

  async function disconnect(folder: ConnectedFolder): Promise<void> {
    try {
      await api.folders.disconnect(projectId, folder.id);
      await loadConnected();
    } catch (err) {
      fail(err, 'Could not disconnect that folder.');
    }
  }

  async function upload(): Promise<void> {
    if (!files || files.length === 0) return;
    busy = true;
    error = '';
    summary = [];
    notes = [];
    const list = [...files];
    let added = 0;
    for (const [i, file] of list.entries()) {
      progress = i / list.length;
      try {
        await api.images.upload(projectId, file);
        added++;
        changed = true;
      } catch (err) {
        notes.push({ subject: file.name, reason: err instanceof ApiError ? err.message : 'Upload failed.' });
      }
    }
    progress = 1;
    summary = [`${plural(added, 'image')} uploaded.`, notes.length ? `${plural(notes.length, 'file')} skipped.` : ''].filter(Boolean);
    busy = false;
  }

  async function importLabels(): Promise<void> {
    busy = true;
    error = '';
    summary = [];
    notes = [];
    progress = 0;
    try {
      const started = await api.jobs.importDataset(projectId, labelPath.trim(), format || undefined);
      const job = await waitForJob(started.id, (p) => (progress = p));
      if (job.status === 'failed') {
        error = job.error ?? 'The import failed.';
        return;
      }
      const r = job.result as {
        images_matched: number;
        splits_set: number;
        unmatched_images: number;
        shapes_added: number;
        classes_created: string[];
        notes: Note[];
      };
      changed = true;
      summary = [
        `${plural(r.shapes_added, 'shape')} added to ${plural(r.images_matched, 'image')}.`,
        r.unmatched_images ? `${plural(r.unmatched_images, 'label file')} had no matching image.` : '',
        r.splits_set ? `${plural(r.splits_set, 'image')} put in the train, validation or test split the dataset used.` : '',
        r.classes_created.length ? `New classes: ${r.classes_created.join(', ')}.` : '',
      ].filter(Boolean);
      notes = r.notes;
    } catch (err) {
      fail(err, 'Could not start the import.');
    } finally {
      busy = false;
    }
  }

  function close(): void {
    if (changed) ondone();
    onclose();
  }
</script>

<Modal
  title="Import"
  description="Add images first, then import label files that match them by filename."
  width={560}
  onclose={close}
>
  <TipCard id="dialog:import" />
  <div class="tabs" role="tablist">
    {#each [['images', 'Images'], ['labels', 'Labels']] as const as [id, label] (id)}
      <button
        type="button"
        role="tab"
        aria-selected={tab === id}
        class:active={tab === id}
        disabled={busy}
        onclick={() => (tab = id)}>{label}</button
      >
    {/each}
  </div>

  {#if tab === 'images'}
    <div class="section">
      {#if connected.length > 0}
        <ul class="connected" aria-label="Connected folders">
          {#each connected as f (f.id)}
            <li>
              <span class="path" title={f.path}>{f.path}</span>
              <button type="button" class="tool" disabled={busy} aria-label="Look for new images in {f.path}" title="Look for new images" onclick={() => rescan(f)}><RefreshCw size={14} /></button>
              <button type="button" class="tool" disabled={busy} aria-label="Disconnect {f.path}" title="Disconnect. Images stay in the project." onclick={() => disconnect(f)}><X size={14} /></button>
            </li>
          {/each}
        </ul>
      {/if}
      {#if picking}
        <FolderPicker onpick={connectFolder} oncancel={() => (picking = false)} />
      {:else}
        <div><Button variant="primary" loading={busy} onclick={() => (picking = true)}><FolderOpen size={16} />Connect a folder</Button></div>
        <p class="note">Katib reads the images where they are. Nothing is copied or changed. Connect a folder once, then use the refresh button to pick up new photos.</p>
      {/if}
      <details class="typed">
        <summary>Type a folder path instead</summary>
        <TextField label="Folder on the Katib computer" placeholder="/data/photos" bind:value={typedFolder} />
        <div><Button disabled={busy || !typedFolder.trim()} onclick={() => connectFolder(typedFolder.trim())}>Connect</Button></div>
      </details>
    </div>
    <div class="section">
      <label class="upload">
        <span>Or upload from this device</span>
        <input type="file" multiple accept="image/jpeg,image/png,image/webp,image/bmp,image/tiff" bind:files />
      </label>
      <div><Button loading={busy} disabled={!files || files.length === 0} onclick={upload}>Upload {files && files.length ? plural(files.length, 'file') : ''}</Button></div>
    </div>
  {:else}
    <div class="section">
      <TextField
        label="Label folder or file"
        placeholder="/data/labels"
        bind:value={labelPath}
        hint="A YOLO folder with data.yaml and labels, or a COCO .json file."
      />
      <label class="select">
        <span>Format</span>
        <select bind:value={format}>
          <option value="">Detect automatically</option>
          {#each formats as f (f.id)}<option value={f.id}>{f.label}</option>{/each}
        </select>
      </label>
      <p class="note">Images that already have shapes are skipped, so importing the same file twice does not duplicate anything.</p>
      <div><Button variant="primary" loading={busy} disabled={!labelPath.trim()} onclick={importLabels}>Import labels</Button></div>
    </div>
  {/if}

  {#if busy}
    <div class="bar" role="progressbar" aria-label="Import progress" aria-valuemin="0" aria-valuemax="100" aria-valuenow={Math.round(progress * 100)}>
      <span style:width="{Math.round(progress * 100)}%"></span>
    </div>
  {/if}
  {#if error}<Callout tone="danger">{error}</Callout>{/if}
  {#if summary.length}
    <Callout>
      {#each summary as line (line)}<p class="line">{line}</p>{/each}
    </Callout>
  {/if}
  {#if notes.length}
    <details class="notes">
      <summary>{plural(notes.length, 'note')} about skipped items</summary>
      <ul>
        {#each notes as n, i (i)}<li><span class="mono">{n.subject}</span> {n.reason}</li>{/each}
      </ul>
    </details>
  {/if}

  {#snippet footer()}
    <Button variant="primary" onclick={close}>Done</Button>
  {/snippet}
</Modal>

<style>
  .tabs {
    display: flex;
    gap: var(--space-1);
    margin-block-end: var(--space-3);
    padding: 2px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius-group);
    width: fit-content;
  }

  .tabs button {
    height: 28px;
    padding-inline: var(--space-3);
    background: transparent;
    border: 0;
    border-radius: var(--radius-control);
    color: var(--text-2);
    cursor: pointer;
  }

  .tabs button.active {
    color: var(--accent-text);
    background: var(--accent-muted);
  }

  .section {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    margin-block-end: var(--space-4);
  }

  .upload,
  .select {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    font-weight: 500;
  }

  .select select {
    height: var(--h-input);
    padding-inline: var(--space-2);
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
  }

  .note {
    margin: 0;
    font-size: var(--text-small);
    color: var(--text-2);
  }

  .connected {
    margin: 0;
    padding: 0;
    list-style: none;
    border: 1px solid var(--border);
    border-radius: var(--radius-control);
  }

  .connected li {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) var(--space-2);
    border-block-end: 1px solid var(--border);
  }

  .connected li:last-child {
    border-block-end: 0;
  }

  .path {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    font-family: var(--font-mono);
    font-size: var(--text-small);
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .tool {
    display: grid;
    place-items: center;
    width: var(--h-icon-sm);
    height: var(--h-icon-sm);
    color: var(--text-2);
    background: transparent;
    border: 0;
    cursor: pointer;
  }

  .typed {
    color: var(--text-2);
    font-size: var(--text-small);
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

  .line {
    margin: 0;
  }

  .notes {
    margin-block-start: var(--space-3);
    font-size: var(--text-small);
    color: var(--text-2);
  }

  .notes ul {
    max-height: 160px;
    margin: var(--space-2) 0 0;
    padding-inline-start: var(--space-4);
    overflow-y: auto;
  }
</style>
