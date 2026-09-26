<script lang="ts">
  import { ArrowUp, Folder, FolderOpen } from '@lucide/svelte';
  import { api, ApiError } from '../../lib/api/client';
  import type { FolderListing } from '../../lib/api/types';
  import { plural } from '../../lib/format';
  import Button from '../../lib/ui/Button.svelte';

  let { onpick, oncancel }: { onpick: (path: string) => void; oncancel: () => void } = $props();

  let listing = $state<FolderListing | null>(null);
  let error = $state('');
  let loading = $state(true);

  async function open(path?: string): Promise<void> {
    loading = true;
    error = '';
    try {
      listing = await api.folders.browse(path);
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not open that folder.';
    } finally {
      loading = false;
    }
  }

  $effect(() => {
    void open();
  });

  const atStart = $derived(listing !== null && listing.path === null);
</script>

<div class="picker">
  <div class="bar">
    <button
      type="button"
      class="up"
      aria-label="Up one folder"
      disabled={atStart || loading}
      onclick={() => open(listing?.parent ?? undefined)}><ArrowUp size={16} /></button
    >
    <span class="here" title={listing?.path ?? ''}>{listing?.path ?? 'Choose where to look'}</span>
  </div>

  {#if error}<p class="error" role="alert">{error}</p>{/if}

  {#if listing && listing.path === null}
    {#if listing.places.length === 0}
      <p class="empty">
        No folders are available yet. An administrator can add one under Settings, then Storage,
        as a folder everyone may import from.
      </p>
    {/if}
    <ul class="list" aria-label="Places">
      {#each listing.places as place (place.path)}
        <li>
          <button type="button" onclick={() => open(place.path)}><Folder size={16} />{place.name}</button>
        </li>
      {/each}
    </ul>
  {:else if listing}
    <ul class="list" aria-label="Folders">
      {#each listing.folders as folder (folder.path)}
        <li>
          <button type="button" onclick={() => open(folder.path)}><Folder size={16} />{folder.name}</button>
        </li>
      {:else}
        <li class="empty">No folders inside this one.</li>
      {/each}
    </ul>
    <div class="choose">
      <span class="count">
        {plural(listing.images_here, 'image')} here. Images in the folders inside are included too.
      </span>
      <div class="buttons">
        <Button onclick={oncancel}>Cancel</Button>
        <Button variant="primary" disabled={!listing.can_connect} onclick={() => onpick(listing?.path ?? '')}
          ><FolderOpen size={16} />Use this folder</Button
        >
      </div>
    </div>
  {/if}

  {#if listing && listing.path === null}
    <div class="buttons"><Button onclick={oncancel}>Cancel</Button></div>
  {/if}
</div>

<style>
  .picker {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding: var(--space-3);
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: var(--radius-card);
  }

  .bar {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .up {
    display: grid;
    place-items: center;
    width: var(--h-icon-sm);
    height: var(--h-icon-sm);
    color: var(--text-2);
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
    cursor: pointer;
  }

  .up:disabled {
    opacity: 0.4;
    cursor: default;
  }

  .here {
    flex: 1;
    min-width: 0;
    overflow: hidden;
    font-family: var(--font-mono);
    font-size: var(--text-small);
    text-overflow: ellipsis;
    white-space: nowrap;
    direction: rtl;
    text-align: start;
  }

  .list {
    max-height: 220px;
    margin: 0;
    padding: 0;
    overflow-y: auto;
    list-style: none;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius-control);
  }

  .list button {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    padding: var(--space-2) var(--space-3);
    color: var(--text);
    text-align: start;
    background: transparent;
    border: 0;
    cursor: pointer;
  }

  .list button:hover {
    background: var(--accent-muted);
  }

  .empty,
  .count {
    margin: 0;
    padding: var(--space-2) var(--space-3);
    color: var(--text-2);
    font-size: var(--text-small);
  }

  .count {
    padding: 0;
  }

  .error {
    margin: 0;
    color: var(--danger);
    font-size: var(--text-small);
  }

  .choose {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
  }

  .buttons {
    display: flex;
    gap: var(--space-2);
  }
</style>
