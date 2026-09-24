<script lang="ts">
  import { Eye, EyeOff, Lock, LockOpen, Plus, Tags } from '@lucide/svelte';
  import { ApiError } from '../../lib/api/client';
  import type { Workspace } from '../../lib/state/workspace.svelte';
  import Button from '../../lib/ui/Button.svelte';
  import EmptyState from '../../lib/ui/EmptyState.svelte';
  import IconButton from '../../lib/ui/IconButton.svelte';

  let { ws, onmanage }: { ws: Workspace; onmanage: () => void } = $props();

  let name = $state('');
  let error = $state('');
  let busy = $state(false);

  async function add(): Promise<void> {
    if (busy || !name.trim()) return;
    busy = true;
    error = '';
    try {
      await ws.addClass(name);
      name = '';
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not add the class.';
    } finally {
      busy = false;
    }
  }
</script>

<div class="panel">
  <form
    class="add"
    onsubmit={(e) => {
      e.preventDefault();
      void add();
    }}
  >
    <input
      placeholder="New class name"
      aria-label="New class name"
      aria-invalid={error ? 'true' : undefined}
      bind:value={name}
    />
    <Button variant="primary" disabled={busy || !name.trim()} onclick={add}><Plus size={16} />Add</Button>
  </form>
  {#if error}<p class="error" role="alert">{error}</p>{/if}

  {#if ws.classes.length === 0}
    <EmptyState
      title="No classes yet"
      description="A class is a label such as “car” or “person”. Add one, then draw shapes with it."
    >
      {#snippet icon()}<Tags size={20} />{/snippet}
    </EmptyState>
  {:else}
    <ul>
      {#each ws.classes as cls, i (cls.id)}
        <li class:active={cls.id === ws.activeClassId}>
          <button type="button" class="row" onclick={() => ws.chooseClass(cls.id)}>
            <span class="swatch" style:background={cls.color}></span>
            <span class="name" title={cls.name}>{cls.name}</span>
            <span class="count mono">{cls.annotation_count.toLocaleString()}</span>
            {#if i < 9}<kbd>{i + 1}</kbd>{/if}
          </button>
          <IconButton
            label={ws.hiddenClasses.has(cls.id) ? `Show ${cls.name}` : `Hide ${cls.name}`}
            onclick={() => ws.toggleHidden(cls.id)}
          >
            {#if ws.hiddenClasses.has(cls.id)}<EyeOff size={14} />{:else}<Eye size={14} />{/if}
          </IconButton>
          <IconButton
            label={ws.lockedClasses.has(cls.id) ? `Unlock ${cls.name}` : `Lock ${cls.name}`}
            onclick={() => ws.toggleLocked(cls.id)}
          >
            {#if ws.lockedClasses.has(cls.id)}<Lock size={14} />{:else}<LockOpen size={14} />{/if}
          </IconButton>
        </li>
      {/each}
    </ul>
    <div class="foot">
      <Button onclick={onmanage}>Manage classes...</Button>
    </div>
  {/if}
</div>

<style>
  .panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding: var(--space-3);
  }

  .add {
    display: flex;
    gap: var(--space-2);
  }

  input {
    flex: 1;
    min-width: 0;
    height: var(--h-button-sm);
    padding-inline: var(--space-2);
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
  }

  input[aria-invalid='true'] {
    border-color: var(--danger);
  }

  .error {
    margin: 0;
    color: var(--danger);
    font-size: var(--text-small);
  }

  ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: flex;
    align-items: center;
    border-radius: var(--radius-control);
  }

  li:hover {
    background: var(--surface-2);
  }

  li.active {
    background: var(--accent-muted);
  }

  .row {
    display: flex;
    flex: 1;
    align-items: center;
    gap: var(--space-2);
    min-width: 0;
    height: var(--h-button);
    padding: 0 var(--space-2);
    text-align: start;
    background: transparent;
    border: 0;
    cursor: pointer;
  }

  .swatch {
    flex: none;
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

  kbd {
    min-width: 18px;
    padding-inline: 4px;
    font-family: var(--font-mono);
    font-size: var(--text-overline);
    color: var(--text-2);
    text-align: center;
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-chip);
  }

  .foot {
    padding-block-start: var(--space-2);
  }
</style>
