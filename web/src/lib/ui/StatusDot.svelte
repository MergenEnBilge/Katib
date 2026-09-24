<script lang="ts">
  import { Check } from '@lucide/svelte';

  let { status }: { status: string } = $props();

  const labels: Record<string, string> = {
    todo: 'Not started',
    in_progress: 'In progress',
    done: 'Done',
    approved: 'Approved',
    rejected: 'Rejected',
  };
</script>

<span class="dot {status}" role="img" aria-label={labels[status] ?? status} title={labels[status] ?? status}>
  {#if status === 'approved'}<Check size={7} strokeWidth={3.5} />{/if}
</span>

<style>
  .dot {
    display: inline-grid;
    place-items: center;
    flex: none;
    width: 9px;
    height: 9px;
    border: 1.5px solid var(--text-3);
    border-radius: 50%;
    box-sizing: border-box;
  }

  .in_progress {
    border-color: var(--accent);
  }

  .done,
  .approved {
    background: var(--accent);
    border-color: var(--accent);
    color: var(--on-accent);
  }

  .rejected {
    background: var(--danger);
    border-color: var(--danger);
  }
</style>
