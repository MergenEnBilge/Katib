<script lang="ts">
  let { label, shortcut }: { label: string; shortcut?: string } = $props();
</script>

<span class="tooltip" role="tooltip">
  {label}
  {#if shortcut}<kbd>{shortcut}</kbd>{/if}
</span>

<style>
  .tooltip {
    position: absolute;
    inset-block-start: calc(100% + var(--space-1));
    inset-inline-start: 50%;
    transform: translateX(-50%);
    /* Not laid out until needed, so a tooltip at the screen edge cannot widen the page. */
    display: none;
    align-items: center;
    gap: var(--space-2);
    height: 26px;
    padding-inline: var(--space-2);
    white-space: nowrap;
    font-size: var(--text-small);
    color: var(--text);
    background: var(--surface-2);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
    box-shadow: var(--shadow);
    z-index: var(--z-tooltip);
    pointer-events: none;
    opacity: 0;
    transition: opacity 0ms linear 0ms;
  }

  /* Shown by the parent's hover or keyboard focus, after a 400ms delay. */
  :global(.has-tooltip:hover) > .tooltip,
  :global(.has-tooltip:focus-visible) > .tooltip {
    display: inline-flex;
    /* Waits 400ms before appearing, so it does not flash as the pointer passes. */
    animation: tip-in 1ms linear 400ms backwards;
    opacity: 1;
  }

  @keyframes tip-in {
    from {
      opacity: 0;
    }
  }

  kbd {
    font-family: var(--font-mono);
    font-size: var(--text-overline);
    color: var(--text-3);
    border: 1px solid var(--border);
    border-radius: var(--radius-chip);
    min-width: 18px;
    padding-inline: 4px;
    text-align: center;
  }
</style>
