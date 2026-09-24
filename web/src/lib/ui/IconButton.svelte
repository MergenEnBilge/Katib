<script lang="ts">
  import type { Snippet } from 'svelte';
  import Tooltip from './Tooltip.svelte';

  let {
    label,
    shortcut,
    onclick,
    children,
  }: { label: string; shortcut?: string; onclick?: () => void; children: Snippet } = $props();
</script>

<button class="icon-button has-tooltip" type="button" aria-label={label} {onclick}>
  {@render children()}
  <Tooltip {label} {shortcut} />
</button>

<style>
  .icon-button {
    position: relative;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: var(--h-icon);
    height: var(--h-icon);
    padding: 0;
    color: var(--text-2);
    background: transparent;
    border: 0;
    border-radius: var(--radius-control);
    cursor: pointer;
    transition:
      background var(--dur-hover) ease-out,
      color var(--dur-hover) ease-out;
  }

  .icon-button:hover {
    color: var(--text);
    background: var(--surface-2);
  }
</style>
