<script lang="ts">
  import { ImageIcon, PanelLeft, Upload } from '@lucide/svelte';
  import { api } from '../../lib/api/client';
  import { plural } from '../../lib/format';
  import type { StatusFilter, Workspace } from '../../lib/state/workspace.svelte';
  import Button from '../../lib/ui/Button.svelte';
  import Callout from '../../lib/ui/Callout.svelte';
  import EmptyState from '../../lib/ui/EmptyState.svelte';
  import IconButton from '../../lib/ui/IconButton.svelte';
  import StatusDot from '../../lib/ui/StatusDot.svelte';

  let {
    ws,
    collapsed,
    ontoggle,
    onimport,
  }: { ws: Workspace; collapsed: boolean; ontoggle: () => void; onimport: () => void } = $props();

  const ROW = 48;
  const OVERSCAN = 6;

  let scroller: HTMLDivElement | undefined = $state();
  let scrollTop = $state(0);
  let viewHeight = $state(400);
  let search = $state('');

  const chips: { id: StatusFilter; label: string }[] = [
    { id: 'all', label: 'All' },
    { id: 'todo', label: 'Not started' },
    { id: 'in_progress', label: 'In progress' },
    { id: 'done', label: 'Done' },
  ];

  const first = $derived(Math.max(0, Math.floor(scrollTop / ROW) - OVERSCAN));
  const last = $derived(
    Math.min(ws.images.length, Math.ceil((scrollTop + viewHeight) / ROW) + OVERSCAN),
  );
  const visible = $derived(ws.images.slice(first, last));

  $effect(() => {
    void search;
    const timer = setTimeout(() => {
      if (search !== ws.search) void ws.setFilter(ws.statusFilter, search);
    }, 250);
    return () => clearTimeout(timer);
  });

  function onscroll(): void {
    if (!scroller) return;
    scrollTop = scroller.scrollTop;
    viewHeight = scroller.clientHeight;
    if (ws.imagesNext && last >= ws.images.length - 10) void ws.loadImages(false);
  }

  $effect(() => {
    if (scroller) viewHeight = scroller.clientHeight;
  });

  $effect(() => {
    // Keep the open image in view when moving with the keyboard.
    const index = ws.currentIndex;
    if (!scroller || index < 0) return;
    const top = index * ROW;
    if (top < scroller.scrollTop) scroller.scrollTop = top;
    else if (top + ROW > scroller.scrollTop + scroller.clientHeight) {
      scroller.scrollTop = top + ROW - scroller.clientHeight;
    }
  });
</script>

<aside class="rail" class:collapsed aria-label="Images">
  <header>
    {#if !collapsed}
      <span class="count mono">{plural(ws.project?.image_count ?? 0, 'image')}</span>
    {/if}
    <IconButton label={collapsed ? 'Expand image list' : 'Collapse image list'} shortcut="[" onclick={ontoggle}>
      <PanelLeft size={16} class="mirror" />
    </IconButton>
  </header>

  {#if !collapsed}
    <div class="filters">
      <input
        type="search"
        placeholder="Filter by filename"
        aria-label="Filter by filename"
        bind:value={search}
      />
      <div class="chips" role="group" aria-label="Filter by status">
        {#each chips as chip (chip.id)}
          <button
            type="button"
            class="chip"
            class:active={ws.statusFilter === chip.id}
            aria-pressed={ws.statusFilter === chip.id}
            onclick={() => ws.setFilter(chip.id, ws.search)}
          >
            {chip.label}
            {#if chip.id === 'all' && ws.project}<span class="mono">{ws.project.image_count.toLocaleString()}</span>{/if}
            {#if chip.id === 'done' && ws.project}<span class="mono">{ws.project.done_count.toLocaleString()}</span>{/if}
          </button>
        {/each}
      </div>
    </div>
  {/if}

  {#if ws.loadError}
    <div class="pad">
      <Callout tone="danger">
        {ws.loadError}
        {#snippet action()}<Button onclick={() => ws.loadImages(true)}>Try again</Button>{/snippet}
      </Callout>
    </div>
  {:else if ws.images.length === 0 && ws.imagesLoading}
    <div class="skeletons" aria-busy="true">
      {#each [1, 2, 3, 4, 5, 6] as n (n)}<div class="sk"></div>{/each}
    </div>
  {:else if ws.images.length === 0 && !collapsed}
    <div class="pad">
      {#if ws.search || ws.statusFilter !== 'all'}
        <p class="none">No images match this filter.</p>
      {:else}
        <EmptyState
          title="No images yet"
          description="Add images from a folder on this computer or upload them from this device."
        >
          {#snippet icon()}<ImageIcon size={20} />{/snippet}
          {#snippet action()}
            <Button variant="primary" onclick={onimport}><Upload size={16} />Import images</Button>
          {/snippet}
        </EmptyState>
      {/if}
    </div>
  {:else}
    <div class="list" bind:this={scroller} {onscroll}>
      <div class="space" style:height="{ws.images.length * ROW}px">
        <ul style:transform="translateY({first * ROW}px)">
          {#each visible as image (image.id)}
            <li>
              <button
                type="button"
                class="row"
                class:selected={image.id === ws.currentId}
                aria-current={image.id === ws.currentId ? 'true' : undefined}
                title={image.filename}
                onclick={() => ws.open(image.id)}
              >
                <img src={api.images.thumbUrl(image.id)} alt="" loading="lazy" width="48" height="32" />
                {#if !collapsed}
                  <span class="text">
                    <span class="name mono">{image.filename}</span>
                    <span class="meta">{plural(image.annotation_count, 'shape')}</span>
                  </span>
                  <StatusDot status={image.status} />
                {/if}
              </button>
            </li>
          {/each}
        </ul>
      </div>
    </div>
  {/if}
</aside>

<style>
  .rail {
    display: flex;
    flex-direction: column;
    width: 280px;
    min-height: 0;
    background: var(--surface-1);
    border-inline-end: 1px solid var(--border);
  }

  .rail.collapsed {
    width: 56px;
  }

  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 45px;
    padding-inline: var(--space-3);
    border-block-end: 1px solid var(--border);
  }

  .collapsed header {
    justify-content: center;
    padding-inline: 0;
  }

  .count {
    font-size: var(--text-small);
    color: var(--text-2);
  }

  .filters {
    padding: var(--space-3);
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  input {
    height: var(--h-button-sm);
    padding-inline: var(--space-2);
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
  }

  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
  }

  .chip {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    height: var(--h-chip);
    padding-inline: var(--space-2);
    font-size: var(--text-overline);
    color: var(--text-2);
    background: transparent;
    border: 1px solid var(--border);
    border-radius: var(--radius-chip);
    cursor: pointer;
  }

  .chip.active {
    color: var(--text);
    background: var(--accent-muted);
    border-color: var(--accent-muted);
  }

  .chip .mono {
    color: var(--text-2);
  }

  .list {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
  }

  .space {
    position: relative;
  }

  ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    height: 48px;
    padding: 0 var(--space-2);
  }

  .row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    height: 44px;
    margin-block: 2px;
    padding: 0 var(--space-2);
    text-align: start;
    background: transparent;
    border: 0;
    border-radius: var(--radius-control);
    cursor: pointer;
  }

  .collapsed .row {
    justify-content: center;
    padding: 0;
  }

  .row:hover {
    background: var(--surface-2);
  }

  .row.selected {
    background: var(--accent-muted);
  }

  img {
    flex: none;
    object-fit: cover;
    background: var(--image-bg);
    border: 1px solid var(--border);
    border-radius: var(--radius-chip);
  }

  .text {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: 0;
  }

  .name {
    overflow: hidden;
    font-size: var(--text-small);
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .meta {
    font-size: var(--text-overline);
    color: var(--text-3);
  }

  .selected .meta {
    color: var(--text-2);
  }

  .pad {
    padding: var(--space-3);
  }

  .none {
    color: var(--text-2);
  }

  .skeletons {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding: var(--space-3);
  }

  .sk {
    height: 40px;
    background: var(--surface-2);
    border-radius: var(--radius-control);
  }
</style>
