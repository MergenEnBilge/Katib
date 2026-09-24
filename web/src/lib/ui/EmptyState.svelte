<script lang="ts">
  import type { Snippet } from 'svelte';

  let {
    title,
    description,
    icon,
    action,
  }: { title: string; description: string; icon: Snippet; action?: Snippet } = $props();
</script>

<div class="empty">
  <div class="tile" aria-hidden="true">{@render icon()}</div>
  <h2>{title}</h2>
  <p>{description}</p>
  {#if action}<div class="action">{@render action()}</div>{/if}
</div>

<style>
  .empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
    padding: var(--space-8) var(--space-6);
    border: 1px dashed var(--border-strong);
    border-radius: var(--radius-card);
  }

  .tile {
    display: grid;
    place-items: center;
    width: var(--h-empty-icon);
    height: var(--h-empty-icon);
    color: var(--text-2);
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: var(--radius-card);
  }

  h2 {
    margin: var(--space-3) 0 var(--space-1);
    font-size: var(--text-heading);
    font-weight: 500;
  }

  p {
    margin: 0;
    max-width: 380px;
    color: var(--text-2);
  }

  .action {
    margin-top: var(--space-4);
  }
</style>
