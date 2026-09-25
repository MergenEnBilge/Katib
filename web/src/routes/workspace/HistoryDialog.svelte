<script lang="ts">
  import TipCard from '../../lib/ui/TipCard.svelte';
  import { api, ApiError } from '../../lib/api/client';
  import type { OperationInfo } from '../../lib/api/types';
  import { relativeTime } from '../../lib/format';
  import type { Workspace } from '../../lib/state/workspace.svelte';
  import Button from '../../lib/ui/Button.svelte';
  import Callout from '../../lib/ui/Callout.svelte';
  import Modal from '../../lib/ui/Modal.svelte';

  let { ws, onclose }: { ws: Workspace; onclose: () => void } = $props();

  let items = $state<OperationInfo[] | null>(null);
  let error = $state('');
  let busyId = $state<string | null>(null);

  async function load(): Promise<void> {
    error = '';
    try {
      items = await api.operations.list(ws.projectId);
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not load the history.';
    }
  }

  $effect(() => {
    void load();
  });

  async function undo(id: string): Promise<void> {
    busyId = id;
    await ws.revertOperation(id);
    busyId = null;
    await load();
  }
</script>

<Modal
  title="History"
  description="Bulk changes such as merging or deleting a class. Undo works for 30 days and survives a reload."
  width={560}
  {onclose}
>
  <TipCard id="dialog:history" />
  {#if error}
    <Callout tone="danger">
      {error}
      {#snippet action()}<Button onclick={load}>Try again</Button>{/snippet}
    </Callout>
  {:else if items === null}
    <div class="sk" aria-busy="true"></div>
  {:else if items.length === 0}
    <p class="none">Nothing here yet. Merges, class deletions and bulk edits appear in this list.</p>
  {:else}
    <ul>
      {#each items as op (op.id)}
        <li>
          <div class="text">
            <p class="summary" class:done={op.reverted}>{op.summary}</p>
            <p class="when">{relativeTime(op.created_at)}{op.reverted ? ' - undone' : ''}</p>
          </div>
          {#if op.can_revert}
            <Button disabled={busyId !== null} onclick={() => undo(op.id)}>Undo</Button>
          {:else if !op.reverted}
            <span class="when">Can no longer be undone</span>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
  {#snippet footer()}
    <Button variant="primary" onclick={onclose}>Close</Button>
  {/snippet}
</Modal>

<style>
  ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding-block: var(--space-2);
    border-block-end: 1px solid var(--border);
  }

  .summary {
    margin: 0;
  }

  .summary.done {
    color: var(--text-3);
    text-decoration: line-through;
  }

  .when,
  .none {
    margin: 0;
    font-size: var(--text-small);
    color: var(--text-2);
  }

  .sk {
    height: 96px;
    background: var(--surface-1);
    border-radius: var(--radius-card);
  }
</style>
