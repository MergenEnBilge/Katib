<script lang="ts">
  import { ArrowLeft, Check, Trash } from '@lucide/svelte';
  import { onMount, untrack } from 'svelte';
  import { SvelteSet } from 'svelte/reactivity';
  import { api, ApiError } from '../../lib/api/client';
  import type { ClassOp, Project, ProjectClass, ShapeItem } from '../../lib/api/types';
  import { plural } from '../../lib/format';
  import { announceOperation } from '../../lib/state/operations';
  import { router } from '../../lib/state/router.svelte';
  import { applyTheme } from '../../lib/state/theme.svelte';
  import { toasts } from '../../lib/state/toast.svelte';
  import Button from '../../lib/ui/Button.svelte';
  import Callout from '../../lib/ui/Callout.svelte';
  import EmptyState from '../../lib/ui/EmptyState.svelte';
  import IconButton from '../../lib/ui/IconButton.svelte';
  import Modal from '../../lib/ui/Modal.svelte';
  import Toast from '../../lib/ui/Toast.svelte';

  let { projectId }: { projectId: string } = $props();

  let project = $state<Project | null>(null);
  let classes = $state<ProjectClass[]>([]);
  let items = $state<ShapeItem[]>([]);
  let next = $state<string | null>(null);
  let loading = $state(false);
  let error = $state('');
  let classFilter = $state('');
  let statusFilter = $state('');
  let tinyOnly = $state(false);
  const selected = new SvelteSet<string>();
  let dialog = $state<null | { kind: 'reclass' | 'delete'; target?: string }>(null);
  let preview = $state<ClassOp | null>(null);
  let busy = $state(false);
  let sentinel: HTMLDivElement | undefined = $state();
  let version = 0;

  $effect(applyTheme);

  const classOf = (id: string | null | undefined): ProjectClass | undefined =>
    classes.find((c) => c.id === id);

  async function load(reset: boolean): Promise<void> {
    if (loading) return;
    loading = true;
    error = '';
    const mine = reset ? ++version : version;
    try {
      const page = await api.shapes.list(projectId, {
        class_id: classFilter || undefined,
        image_status: statusFilter || undefined,
        tiny_only: tinyOnly || undefined,
        after: reset ? undefined : next,
        limit: 60,
      });
      if (mine !== version) return;
      items = reset ? page.items : [...items, ...page.items];
      next = page.next ?? null;
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not load shapes.';
    } finally {
      loading = false;
    }
  }

  onMount(() => {
    (async () => {
      try {
        [project, classes] = await Promise.all([
          api.projects.get(projectId),
          api.classes.list(projectId),
        ]);
      } catch (err) {
        error = err instanceof ApiError ? err.message : 'Could not open this project.';
        return;
      }
      await load(true);
    })();
  });

  $effect(() => {
    void classFilter;
    void statusFilter;
    void tinyOnly;
    // Only the three filters should re-run this. Clearing the selection would otherwise
    // subscribe to it, and every click on a tile would reset the list.
    untrack(() => {
      selected.clear();
      if (project) void load(true);
    });
  });

  $effect(() => {
    if (!sentinel) return;
    const observer = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting) && next && !loading) void load(false);
    });
    observer.observe(sentinel);
    return () => observer.disconnect();
  });

  function toggle(id: string): void {
    if (!selected.delete(id)) selected.add(id);
  }

  async function askPreview(kind: 'reclass' | 'delete', target?: string): Promise<void> {
    dialog = { kind, target };
    preview = null;
    try {
      preview = await api.shapes.bulk(projectId, {
        action: kind,
        ids: [...selected],
        target_id: target,
        dry_run: true,
      });
    } catch (err) {
      toasts.show(err instanceof ApiError ? err.message : 'Could not preview that.');
      dialog = null;
    }
  }

  async function confirm(): Promise<void> {
    if (!dialog || busy) return;
    busy = true;
    try {
      const done = await api.shapes.bulk(projectId, {
        action: dialog.kind,
        ids: [...selected],
        target_id: dialog.target,
        dry_run: false,
      });
      announceOperation(done.operation?.summary ?? 'Done.', done.operation?.id, () => refresh());
      dialog = null;
      selected.clear();
      await refresh();
    } catch (err) {
      toasts.show(err instanceof ApiError ? err.message : 'That did not work.');
    } finally {
      busy = false;
    }
  }

  async function refresh(): Promise<void> {
    classes = await api.classes.list(projectId);
    await load(true);
  }

  const targetName = $derived(dialog?.target ? classOf(dialog.target)?.name : '');
</script>

<div class="page">
  <header class="bar">
    <IconButton label="Back to the workspace" onclick={() => router.navigate(`/p/${projectId}`)}>
      <ArrowLeft size={16} class="mirror" />
    </IconButton>
    <h1>{project?.name ?? 'Loading'} <span class="sub">Class gallery</span></h1>
  </header>

  <div class="filters">
    <label>
      <span>Class</span>
      <select bind:value={classFilter}>
        <option value="">All classes</option>
        {#each classes as c (c.id)}<option value={c.id}>{c.name} ({c.annotation_count.toLocaleString()})</option>{/each}
      </select>
    </label>
    <label>
      <span>Image status</span>
      <select bind:value={statusFilter}>
        <option value="">Any</option>
        <option value="todo">Not started</option>
        <option value="in_progress">In progress</option>
        <option value="done">Done</option>
      </select>
    </label>
    <label class="check"><input type="checkbox" bind:checked={tinyOnly} /> Tiny shapes only</label>
    <span class="grow"></span>
    {#if selected.size > 0}
      <span class="count mono">{plural(selected.size, 'shape')} selected</span>
      <select
        aria-label="Change class of the selection"
        onchange={(e) => {
          const id = e.currentTarget.value;
          e.currentTarget.value = '';
          if (id) void askPreview('reclass', id);
        }}
      >
        <option value="">Change class...</option>
        {#each classes as c (c.id)}<option value={c.id}>{c.name}</option>{/each}
      </select>
      <Button variant="danger-quiet" onclick={() => askPreview('delete')}><Trash size={16} />Delete...</Button>
      {#if selected.size === 1}
        {@const only = items.find((i) => selected.has(i.id))}
        {#if only}
          <Button onclick={() => router.navigate(`/p/${projectId}?image=${only.image_id}`)}>Open in image</Button>
        {/if}
      {/if}
      <Button onclick={() => selected.clear()}>Clear</Button>
    {:else if items.length > 0}
      <Button onclick={() => items.forEach((i) => selected.add(i.id))}>Select all {items.length.toLocaleString()} loaded</Button>
    {/if}
  </div>

  <main>
    {#if error}
      <Callout tone="danger">
        {error}
        {#snippet action()}<Button onclick={() => load(true)}>Try again</Button>{/snippet}
      </Callout>
    {:else if items.length === 0 && loading}
      <div class="grid" aria-busy="true">{#each [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] as n (n)}<div class="skeleton"></div>{/each}</div>
    {:else if items.length === 0}
      <EmptyState
        title="No shapes match"
        description="Shapes from every image appear here as crops, so you can review one class at a time and fix mistakes in bulk."
      >
        {#snippet icon()}<Check size={20} />{/snippet}
      </EmptyState>
    {:else}
      <div class="grid">
        {#each items as item (item.id)}
          {@const cls = classOf(item.class_id)}
          <button
            type="button"
            class="tile"
            class:on={selected.has(item.id)}
            aria-pressed={selected.has(item.id)}
            onclick={() => toggle(item.id)}
          >
            <img src={api.shapes.cropUrl(item.id)} alt="{cls?.name ?? 'Shape'} in {item.filename}" loading="lazy" />
            <span class="cap">
              <span class="swatch" style:background={cls?.color}></span>
              <span class="name">{cls?.name ?? 'No class'}</span>
            </span>
            {#if selected.has(item.id)}<span class="tick"><Check size={12} strokeWidth={3} /></span>{/if}
          </button>
        {/each}
      </div>
      <div bind:this={sentinel} class="sentinel">{#if loading}Loading more...{/if}</div>
    {/if}
  </main>
</div>

{#if dialog}
  <Modal
    title={dialog.kind === 'delete' ? 'Delete shapes' : 'Change class'}
    width={440}
    onclose={() => (dialog = null)}
  >
    {#if !preview}
      <p class="none">Counting...</p>
    {:else if dialog.kind === 'delete'}
      <Callout tone="danger">
        This will delete {plural(preview.preview.annotations, 'annotation')} on {plural(preview.preview.images, 'image')}.
      </Callout>
    {:else}
      <Callout>
        {plural(preview.preview.annotations, 'annotation')} on {plural(preview.preview.images, 'image')} will be relabeled as “{targetName}”.
      </Callout>
    {/if}
    {#snippet footer()}
      <Button onclick={() => (dialog = null)}>Cancel</Button>
      <Button
        variant={dialog?.kind === 'delete' ? 'danger' : 'primary'}
        disabled={!preview || busy}
        onclick={confirm}
      >
        {dialog?.kind === 'delete' ? 'Delete' : 'Change class'}
      </Button>
    {/snippet}
  </Modal>
{/if}

<Toast />

<style>
  .page {
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  .bar {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    height: 48px;
    padding-inline: var(--space-3);
    background: var(--surface-1);
    border-block-end: 1px solid var(--border);
  }

  h1 {
    margin: 0;
    font-size: var(--text-heading);
    font-weight: 500;
  }

  .sub {
    margin-inline-start: var(--space-2);
    font-weight: 400;
    color: var(--text-2);
  }

  .filters {
    display: flex;
    flex-wrap: wrap;
    align-items: end;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
    border-block-end: 1px solid var(--border);
  }

  .filters label {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    font-size: var(--text-small);
    color: var(--text-2);
  }

  .filters .check {
    flex-direction: row;
    align-items: center;
    height: var(--h-button-sm);
  }

  select {
    height: var(--h-button-sm);
    padding-inline: var(--space-2);
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
  }

  .grow {
    flex: 1;
  }

  .count {
    font-size: var(--text-small);
    color: var(--text-2);
  }

  main {
    flex: 1;
    min-height: 0;
    padding: var(--space-4);
    overflow-y: auto;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: var(--space-3);
  }

  .tile {
    position: relative;
    display: flex;
    flex-direction: column;
    padding: 0;
    overflow: hidden;
    text-align: start;
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: var(--radius-control);
    cursor: pointer;
  }

  .tile:hover {
    border-color: var(--border-strong);
  }

  .tile.on {
    border-color: var(--accent-text);
    background: var(--accent-muted);
  }

  img {
    width: 100%;
    height: 120px;
    object-fit: contain;
    background: var(--image-bg);
  }

  .cap {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: 6px var(--space-2);
    font-size: var(--text-small);
  }

  .swatch {
    width: 10px;
    height: 10px;
    border-radius: var(--radius-swatch);
  }

  .name {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .tick {
    position: absolute;
    inset-block-start: var(--space-2);
    inset-inline-end: var(--space-2);
    display: grid;
    place-items: center;
    width: 16px;
    height: 16px;
    color: var(--on-accent);
    background: var(--accent);
    border-radius: var(--radius-chip);
  }

  .skeleton {
    height: 160px;
    background: var(--surface-2);
    border-radius: var(--radius-control);
  }

  .sentinel {
    height: 32px;
    padding-block: var(--space-2);
    text-align: center;
    color: var(--text-3);
    font-size: var(--text-small);
  }

  .none {
    color: var(--text-2);
  }
</style>
