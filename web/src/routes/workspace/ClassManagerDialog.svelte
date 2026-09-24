<script lang="ts">
  import { ApiError } from '../../lib/api/client';
  import { plural } from '../../lib/format';
  import { DEFAULT_PALETTE } from '../../lib/palette';
  import type { Workspace } from '../../lib/state/workspace.svelte';
  import Button from '../../lib/ui/Button.svelte';
  import Modal from '../../lib/ui/Modal.svelte';

  let { ws, onclose }: { ws: Workspace; onclose: () => void } = $props();

  // svelte-ignore state_referenced_locally
  let selectedId = $state<string | null>(ws.activeClassId ?? ws.classes[0]?.id ?? null);
  let query = $state('');
  let error = $state('');
  let draft = $state('');

  const filtered = $derived(
    ws.classes.filter((c) => c.name.toLowerCase().includes(query.trim().toLowerCase())),
  );
  const selected = $derived(ws.classes.find((c) => c.id === selectedId) ?? null);

  $effect(() => {
    draft = selected?.name ?? '';
    error = '';
  });

  async function rename(): Promise<void> {
    if (!selected || draft.trim() === selected.name) return;
    try {
      await ws.renameClass(selected.id, draft);
      error = '';
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not rename the class.';
    }
  }

  async function recolor(color: string): Promise<void> {
    if (!selected) return;
    try {
      await ws.recolorClass(selected.id, color);
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not change the color.';
    }
  }
</script>

<Modal
  title="Class manager"
  description="Rename or recolor a class. Annotations follow automatically because they point at the class, not its name."
  width={720}
  {onclose}
>
  <div class="layout">
    <div class="left">
      <input type="search" placeholder="Search classes" aria-label="Search classes" bind:value={query} />
      <ul>
        {#each filtered as cls (cls.id)}
          <li>
            <button
              type="button"
              class="row"
              class:selected={cls.id === selectedId}
              onclick={() => (selectedId = cls.id)}
            >
              <span class="swatch" style:background={cls.color}></span>
              <span class="name">{cls.name}</span>
              <span class="count mono">{cls.annotation_count.toLocaleString()}</span>
            </button>
          </li>
        {:else}
          <li class="none">No class matches.</li>
        {/each}
      </ul>
    </div>

    <div class="right">
      {#if selected}
        <label class="field">
          <span>Name</span>
          <input
            bind:value={draft}
            aria-invalid={error ? 'true' : undefined}
            onblur={rename}
            onkeydown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
          />
        </label>
        {#if error}<p class="error" role="alert">{error}</p>{/if}
        <p class="note">
          The old name stays as an alias, so label files that still use it import into this class.
        </p>

        <p class="label">Color</p>
        <div class="swatches">
          {#each DEFAULT_PALETTE as color (color)}
            <button
              type="button"
              class="pick"
              class:on={selected.color.toLowerCase() === color.toLowerCase()}
              style:background={color}
              aria-label="Use {color}"
              aria-pressed={selected.color.toLowerCase() === color.toLowerCase()}
              onclick={() => recolor(color)}
            ></button>
          {/each}
          <input
            class="picker"
            type="color"
            aria-label="Pick another color"
            value={selected.color}
            onchange={(e) => recolor(e.currentTarget.value)}
          />
        </div>

        <p class="label">Usage</p>
        <p class="meta mono">{plural(selected.annotation_count, 'annotation')}</p>
      {:else}
        <p class="note">Choose a class on the left.</p>
      {/if}
    </div>
  </div>
  {#snippet footer()}
    <Button variant="primary" onclick={onclose}>Done</Button>
  {/snippet}
</Modal>

<style>
  .layout {
    display: grid;
    grid-template-columns: 240px 1fr;
    gap: var(--space-4);
    min-height: 320px;
  }

  .left {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    min-height: 0;
  }

  input {
    height: var(--h-button-sm);
    padding-inline: var(--space-2);
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
  }

  input[aria-invalid='true'] {
    border-color: var(--danger);
  }

  ul {
    margin: 0;
    padding: 0;
    overflow-y: auto;
    list-style: none;
  }

  .row {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    height: var(--h-button);
    padding: 0 var(--space-2);
    text-align: start;
    background: transparent;
    border: 0;
    border-radius: var(--radius-control);
    cursor: pointer;
  }

  .row:hover {
    background: var(--surface-1);
  }

  .row.selected {
    background: var(--accent-muted);
  }

  .swatch {
    width: 10px;
    height: 10px;
    border-radius: var(--radius-swatch);
  }

  .name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .count {
    font-size: var(--text-overline);
    color: var(--text-2);
  }

  .none {
    padding: var(--space-2);
    color: var(--text-2);
  }

  .right {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    font-weight: 500;
  }

  .field input {
    height: var(--h-input);
    font-weight: 400;
  }

  .error {
    margin: 0;
    font-size: var(--text-small);
    color: var(--danger);
  }

  .note,
  .meta {
    margin: 0;
    font-size: var(--text-small);
    color: var(--text-2);
  }

  .label {
    margin: var(--space-2) 0 0;
    font-size: var(--text-overline);
    font-weight: 500;
    color: var(--text-3);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .swatches {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
  }

  .pick {
    width: 24px;
    height: 24px;
    border: 2px solid transparent;
    border-radius: var(--radius-chip);
    cursor: pointer;
  }

  .pick.on {
    border-color: var(--text);
  }

  .picker {
    width: 32px;
    padding: 2px;
  }

  @media (max-width: 699px) {
    .layout {
      grid-template-columns: 1fr;
    }
  }
</style>
