<script lang="ts">
  import type { Snippet } from 'svelte';

  let {
    variant = 'secondary',
    disabled = false,
    onclick,
    children,
  }: {
    variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'danger-quiet';
    disabled?: boolean;
    onclick?: () => void;
    children: Snippet;
  } = $props();
</script>

<button class="button {variant}" type="button" {disabled} {onclick}>
  {@render children()}
</button>

<style>
  .button {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    height: var(--h-button);
    padding-inline: var(--space-3);
    font-weight: 500;
    border-radius: var(--radius-control);
    border: 1px solid transparent;
    cursor: pointer;
    transition:
      background var(--dur-hover) ease-out,
      border-color var(--dur-hover) ease-out,
      color var(--dur-hover) ease-out;
  }

  .button:disabled {
    opacity: 0.4;
    pointer-events: none;
  }

  .primary {
    background: var(--accent);
    color: var(--on-accent);
  }
  .primary:hover {
    background: var(--accent-hover);
  }

  .secondary {
    background: transparent;
    border-color: var(--border);
  }
  .secondary:hover {
    border-color: var(--border-strong);
    background: var(--surface-1);
  }

  .danger {
    background: var(--danger);
    color: var(--on-danger);
  }
  .danger:hover {
    opacity: 0.9;
  }

  .danger-quiet {
    background: transparent;
    border-color: var(--border);
    color: var(--danger-text);
  }
  .danger-quiet:hover {
    border-color: var(--border-strong);
    background: var(--danger-muted);
  }

  .ghost {
    background: transparent;
    color: var(--text-2);
  }
  .ghost:hover {
    background: var(--surface-2);
    color: var(--text);
  }
</style>
