<script lang="ts">
  import TipCard from '../../lib/ui/TipCard.svelte';
  import { Cloud, FolderOpen, RefreshCw, Upload, X } from '@lucide/svelte';
  import { api, ApiError, waitForJob } from '../../lib/api/client';
  import type { ConnectedFolder, FormatInfo, Job } from '../../lib/api/types';
  import { plural } from '../../lib/format';
  import { knownPictures } from '../../lib/upload/known';
  import Button from '../../lib/ui/Button.svelte';
  import Callout from '../../lib/ui/Callout.svelte';
  import Modal from '../../lib/ui/Modal.svelte';
  import TextField from '../../lib/ui/TextField.svelte';
  import FolderPicker from './FolderPicker.svelte';

  let {
    projectId,
    initialTab = 'images',
    documents = false,
    ondone,
    onclose,
  }: {
    projectId: string;
    initialTab?: 'images' | 'labels';
    /** The project labels text documents rather than pictures, so this adds those instead. */
    documents?: boolean;
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
  let pickingLabels = $state(false);
  let documentInput: HTMLInputElement | null = $state(null);
  let buckets = $state<{ name: string; provider: string }[]>([]);
  let bucket = $state('');
  let bucketPrefix = $state('');

  /** Bring in the pictures under a name in a bucket. They stay in the bucket. */
  async function importFromBucket(): Promise<void> {
    if (!bucket) return;
    startOver();
    try {
      const started = await api.cloud.importInto(projectId, bucket, bucketPrefix.trim());
      await finishImport(started);
    } catch (err) {
      fail(err, 'Could not read that bucket.');
    } finally {
      busy = false;
    }
  }

  /** Add documents from the files someone picked, one file at a time so progress means something. */
  async function addDocuments(list: FileList | null): Promise<void> {
    if (!list || list.length === 0) return;
    startOver();
    const files = [...list];
    let added = 0;
    let spans = 0;
    const found: Note[] = [];
    try {
      for (const [i, file] of files.entries()) {
        currentFile = file.name;
        progress = i / files.length;
        const started = await api.documents.add(projectId, file);
        const done = await waitForJob(started.id);
        if (done.status === 'failed') {
          error = done.error ?? 'The documents could not be added.';
          return;
        }
        const result = done.result as unknown as {
          added: number;
          spans: number;
          skipped: Note[];
        };
        added += result.added;
        spans += result.spans;
        found.push(...result.skipped);
      }
      progress = 1;
      changed = true;
      summary = [
        `${plural(added, 'document')} added.`,
        spans ? `${plural(spans, 'label')} came with them.` : '',
        found.length ? `${plural(found.length, 'line', 'lines')} skipped.` : '',
      ].filter(Boolean);
      notes = found;
    } catch (err) {
      fail(err, 'Could not add those documents.');
    } finally {
      busy = false;
      currentFile = '';
      if (documentInput) documentInput.value = '';
    }
  }

  function chooseLabels(path: string): void {
    labelPath = path;
    pickingLabels = false;
  }
  let format = $state('');
  let formats = $state<FormatInfo[]>([]);
  let busy = $state(false);
  let progress = $state(0);
  let error = $state('');
  let summary = $state<string[]>([]);
  let notes = $state<Note[]>([]);
  let folderInput: HTMLInputElement | null = $state(null);
  let picker: HTMLInputElement | null = $state(null);
  /** The file currently going up, shown next to the progress bar during an upload. */
  let currentFile = $state('');
  let changed = false;

  /** Turns a plain file input into a folder picker. Not a real HTML attribute, so TypeScript
   * has no idea it exists -- setting it by hand here is what browsers actually look for. */
  function asDirectoryPicker(node: HTMLInputElement): void {
    node.setAttribute('webkitdirectory', '');
    node.setAttribute('directory', '');
  }

  $effect(() => {
    api
      .formats()
      // Only the formats that match what this project holds: text, or pictures.
      .then((f) => (formats = f.filter((x) => (x.medium === 'text') === documents)))
      .catch((err: unknown) => {
        error = err instanceof ApiError ? err.message : 'Could not load the list of formats.';
      });
    void loadConnected();
    // Buckets are only offered when somebody has set one up.
    api
      .cloud.names()
      .then((found) => (buckets = found))
      .catch(() => (buckets = []));
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

  /** Pictures a scan found gone from their folder, waiting for a yes to take them out. */
  let missing = $state<{ folder: ConnectedFolder; count: number } | null>(null);

  interface FolderImportResult {
    added: number;
    /** Pictures read from this folder before whose files are no longer there. */
    missing?: number;
    skipped_count: number;
    skipped: { name: string; reason: string }[];
    /** Always set: whether this folder held labels Katib could read, and if not, why. */
    dataset: {
      state: 'read' | 'none' | 'failed';
      reason?: string | null;
      format?: string | null;
      images_matched: number;
      shapes_added: number;
      classes_created: string[];
      splits_set: number;
      unmatched_images: number;
      notes: { subject: string; reason: string }[];
    };
  }

  /** Follow an image import until it ends, then show what happened. */
  async function finishImport(job: Job, folder?: ConnectedFolder): Promise<void> {
    missing = null;
    const done = await waitForJob(job.id, (p) => (progress = p));
    if (done.status === 'failed') {
      error = done.error ?? 'The import failed.';
      return;
    }
    const result = done.result as unknown as FolderImportResult;
    changed = true;
    const dataset = result.dataset;
    if (folder && result.missing) missing = { folder, count: result.missing };
    summary = [
      `${plural(result.added, 'image')} added.`,
      result.skipped_count ? `${plural(result.skipped_count, 'file')} skipped.` : '',
      dataset.state === 'read'
        ? `Labels loaded from ${dataset.format ?? 'the dataset'}: ${plural(dataset.shapes_added, 'shape')}${
            dataset.classes_created.length
              ? `, ${plural(dataset.classes_created.length, 'new class', 'new classes')}`
              : ''
          }.`
        : dataset.state === 'failed'
          ? `Found a dataset, but could not read its labels. ${dataset.reason ?? ''}`
          : 'No labels were found in this folder. The pictures were added without them.',
    ].filter(Boolean);
    notes = [
      ...result.skipped.map((s) => ({ subject: s.name, reason: s.reason })),
      ...(dataset.notes ?? []),
    ];
  }

  async function connectFolder(path: string): Promise<void> {
    picking = false;
    startOver();
    try {
      const made = await api.folders.connect(projectId, path);
      await loadConnected();
      await finishImport(made.job, made.folder);
    } catch (err) {
      fail(err, 'Could not connect that folder.');
    } finally {
      busy = false;
    }
  }

  function relativePath(file: File): string {
    return (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;
  }

  async function uploadFolder(list: FileList | null): Promise<void> {
    if (!list || list.length === 0) return;
    startOver();
    const items = [...list];
    const batch = crypto.randomUUID();
    let kept = 0;
    try {
      // Pictures the project already has are not sent again. Checking costs one small request.
      const known = await knownPictures(projectId, items);
      for (const [i, file] of items.entries()) {
        currentFile = relativePath(file);
        progress = i / items.length;
        if (known.has(file)) continue;
        const result = await api.folders.uploadFile(projectId, batch, file);
        if (result.kept) kept++;
      }
      currentFile = '';
      progress = 1;
      const skipped = known.size;
      if (kept === 0 && skipped === 0) {
        error = 'None of those files could be used. Choose some pictures to upload.';
        return;
      }
      if (kept === 0) {
        summary = [`${plural(skipped, 'picture')} already in this project, so nothing was sent.`];
        return;
      }
      const made = await api.folders.uploadFinish(projectId, batch);
      await loadConnected();
      await finishImport(made.job);
      if (skipped) summary = [...summary, `${plural(skipped, 'picture')} already in this project, not sent again.`];
    } catch (err) {
      fail(err, 'Could not upload those files.');
    } finally {
      busy = false;
      currentFile = '';
      if (folderInput) folderInput.value = '';
      if (picker) picker.value = '';
    }
  }

  async function rescan(folder: ConnectedFolder): Promise<void> {
    startOver();
    try {
      await finishImport(await api.folders.rescan(projectId, folder.id), folder);
    } catch (err) {
      fail(err, 'Could not scan that folder.');
    } finally {
      busy = false;
    }
  }

  async function forgetMissing(): Promise<void> {
    if (!missing) return;
    const { folder } = missing;
    busy = true;
    try {
      const { removed } = await api.folders.forgetMissing(projectId, folder.id);
      changed = true;
      summary = [...summary, `${plural(removed, 'missing picture')} taken out of the project.`];
      missing = null;
    } catch (err) {
      fail(err, 'Could not take those pictures out.');
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
  description={documents
    ? 'Add documents first, then import label files that match them by name.'
    : 'Add images first, then import label files that match them by filename.'}
  width={560}
  onclose={close}
>
  <TipCard id="dialog:import" />
  <div class="tabs" role="tablist">
    {#each [['images', documents ? 'Documents' : 'Images'], ['labels', 'Labels']] as const as [id, label] (id)}
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

  {#if tab === 'images' && documents}
    <div class="section">
      <div class="option">
        <h3>Add documents</h3>
        <p class="note">
          A <code>.txt</code> or <code>.md</code> file becomes one document. A
          <code>.jsonl</code> file holds one document per line, and any spans and tags a line
          already carries come in with it, with their classes.
        </p>
        <div>
          <Button variant="primary" loading={busy} onclick={() => documentInput?.click()}>
            <Upload size={16} />Choose files
          </Button>
        </div>
        <input
          type="file"
          multiple
          hidden
          accept=".txt,.md,.text,.jsonl,.ndjson"
          aria-label="Add documents"
          bind:this={documentInput}
          onchange={(e) => void addDocuments((e.currentTarget as HTMLInputElement).files)}
        />
        <p class="note">
          The same words are only added once, so running a file through twice is safe.
        </p>
      </div>
    </div>
  {:else if tab === 'images'}
    {#if connected.length > 0}
      <div class="section">
        <ul class="connected" aria-label="Connected folders">
          {#each connected as f (f.id)}
            <li>
              <span class="path" title={f.path}>{f.path}</span>
              {#if f.copied}
                <span class="tag" title="Uploaded from another device and kept in Katib's own data folder">Copy in Katib</span>
              {:else}
                <span class="tag read" title="Katib reads the pictures where they are">Read in place</span>
                <button type="button" class="tool" disabled={busy} aria-label="Look for new or missing images in {f.path}" title="Look for new or missing images" onclick={() => rescan(f)}><RefreshCw size={14} /></button>
              {/if}
              <button type="button" class="tool" disabled={busy} aria-label="Disconnect {f.path}" title="Take off this list. Images stay in the project." onclick={() => disconnect(f)}><X size={14} /></button>
            </li>
          {/each}
        </ul>
      </div>
    {/if}

    {#if missing}
      <Callout tone="danger">
        {plural(missing.count, 'picture')} in this project {missing.count === 1 ? 'is' : 'are'} no longer in
        {missing.folder.path} — deleted, renamed or moved. Take {missing.count === 1 ? 'it' : 'them'} out of
        the project, with any shapes drawn on {missing.count === 1 ? 'it' : 'them'}? Nothing on disk is touched.
        {#snippet action()}<Button variant="danger" loading={busy} onclick={forgetMissing}>Take them out</Button>{/snippet}
      </Callout>
    {/if}

    <div class="options">
      <div class="option">
        <h3>Connect a folder</h3>
        <p class="note">
          Nothing is copied: Katib reads the pictures where they already are, and finds new ones
          when you look again. Best on the computer Katib runs on. A container can only see folders
          you mounted into it.
        </p>
        {#if picking}
          <FolderPicker onpick={connectFolder} oncancel={() => (picking = false)} />
        {:else}
          <div><Button variant="primary" loading={busy} onclick={() => (picking = true)}><FolderOpen size={16} />Connect a folder</Button></div>
        {/if}
        <details class="typed">
          <summary>Type a folder path instead</summary>
          <TextField label="Folder on the Katib computer" placeholder="/data/photos" bind:value={typedFolder} />
          <div><Button disabled={busy || !typedFolder.trim()} onclick={() => connectFolder(typedFolder.trim())}>Connect</Button></div>
        </details>
      </div>

      {#if buckets.length > 0}
        <div class="option">
          <h3>From a bucket</h3>
          <p class="note">
            Read pictures straight from cloud storage. They stay in the bucket: Katib keeps their
            thumbnails and fetches a picture when somebody opens it.
          </p>
          <label class="select">
            <span>Bucket</span>
            <select bind:value={bucket} disabled={busy}>
              <option value="">Choose a bucket</option>
              {#each buckets as b (b.name)}<option value={b.name}>{b.name}</option>{/each}
            </select>
          </label>
          <TextField
            label="Only names starting with"
            placeholder="datasets/street/"
            bind:value={bucketPrefix}
          />
          <div>
            <Button variant="primary" loading={busy} disabled={!bucket} onclick={importFromBucket}>
              <Cloud size={16} />Read from the bucket
            </Button>
          </div>
        </div>
      {/if}

      <div class="option">
        <h3>Copy from this device</h3>
        <p class="note">
          For a phone, another computer, or a Katib in a container: the browser sends copies of the
          files, which Katib keeps in its own data folder, so they take up space there too. A whole
          folder brings its subfolders, splits and labels along. Loose files work too, with any
          label files among them matched up the same way.
        </p>
        <div class="row">
          <Button loading={busy} onclick={() => folderInput?.click()}
            ><Upload size={16} />Copy a folder</Button
          >
          <Button loading={busy} onclick={() => picker?.click()}>Copy pictures and labels</Button>
        </div>
        <input
          bind:this={folderInput}
          type="file"
          multiple
          hidden
          aria-label="Copy a folder"
          use:asDirectoryPicker
          onchange={(e) => uploadFolder(e.currentTarget.files)}
        />
        <input
          bind:this={picker}
          type="file"
          multiple
          hidden
          aria-label="Copy pictures and labels"
          accept="image/jpeg,image/png,image/webp,image/bmp,image/tiff,.txt,.json,.xml,.yaml,.yml"
          onchange={(e) => uploadFolder(e.currentTarget.files)}
        />
      </div>
    </div>
  {:else}
    <div class="section">
      <p class="note">
        Choose the dataset folder, or its <code>data.yaml</code> or <code>obj.data</code> file. YOLO
        (old or new, including pose and rotated boxes), COCO, Pascal VOC, LabelMe, CVAT, CreateML,
        mask pictures and class folders are all read, with their splits.
      </p>
      {#if pickingLabels}
        <FolderPicker
          onpick={chooseLabels}
          onpickfile={chooseLabels}
          oncancel={() => (pickingLabels = false)}
        />
      {:else}
        <div class="chosen">
          {#if labelPath}
            <span class="mono" title={labelPath}>{labelPath}</span>
          {:else}
            <span class="note">Nothing chosen yet.</span>
          {/if}
          <Button onclick={() => (pickingLabels = true)}><FolderOpen size={16} />{labelPath ? 'Choose another' : 'Choose labels'}</Button>
        </div>
        <details class="typed">
          <summary>Type a path instead</summary>
          <TextField label="Folder or file on the Katib computer" placeholder="/data/labels" bind:value={labelPath} />
        </details>
      {/if}
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
    {#if currentFile}<p class="current mono">Uploading {currentFile}…</p>{/if}
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

  .options {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-4);
    margin-block-end: var(--space-3);
  }

  @media (max-width: 520px) {
    .options {
      grid-template-columns: 1fr;
    }
  }

  .option {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding: var(--space-3);
    background: var(--surface-2);
    border-radius: var(--radius-card);
  }

  .option h3 {
    margin: 0;
    font-size: var(--text-body);
  }

  .row {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }

  .current {
    margin: 0 0 var(--space-2);
    font-size: var(--text-small);
    color: var(--text-2);
  }

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

  .tag {
    flex: none;
    padding: 1px var(--space-2);
    color: var(--text-2);
    background: var(--surface-2);
    border-radius: var(--radius-control);
    font-size: var(--text-small);
    white-space: nowrap;
  }

  .tag.read {
    color: var(--accent-text);
    background: var(--accent-muted);
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
