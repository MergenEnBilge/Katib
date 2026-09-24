<script lang="ts">
  import type { Snippet } from 'svelte';

  let {
    tone = 'neutral',
    children,
    action,
  }: { tone?: 'neutral' | 'danger'; children: Snippet; action?: Snippet } = $props();
</script>

<div class="callout {tone}" role={tone === 'danger' ? 'alert' : undefined}>
  <div class="text">{@render children()}</div>
  {#if action}<div>{@render action()}</div>{/if}
</div>

<style>
  .callout {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
    padding: 14px var(--space-4);
    border-radius: var(--radius-card);
    border: 1px solid var(--border);
    background: var(--surface-1);
  }

  .danger {
    background: var(--danger-muted);
    border-color: var(--danger);
  }

  .text {
    min-width: 0;
  }
</style>
