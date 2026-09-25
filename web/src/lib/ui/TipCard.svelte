<script lang="ts">
  import { Lightbulb } from '@lucide/svelte';
  import { tips } from '../state/tips.svelte';
  import { TIPS } from '../tour/tips';
  import Button from './Button.svelte';

  /** `floating` sits over the canvas. Otherwise the card takes its place in the page. */
  let { id, floating = false, hold = false }: { id: string; floating?: boolean; hold?: boolean } = $props();

  const tip = $derived(TIPS[id]);
  const show = $derived(!hold && tip !== undefined && tips.shouldShow(id));
</script>

{#if show && tip}
  <aside class="tip" class:floating role="note" aria-label="Tip: {tip.title}">
    <div class="head">
      <Lightbulb size={16} aria-hidden="true" />
      <strong>{tip.title}</strong>
    </div>
    <p class="body">{tip.body}</p>
    {#if tip.points?.length}
      <ul>{#each tip.points as point (point)}<li>{point}</li>{/each}</ul>
    {/if}
    {#if tip.keys?.length}
      <dl>
        {#each tip.keys as k (k.keys)}
          <div><dt class="mono">{k.keys}</dt><dd>{k.does}</dd></div>
        {/each}
      </dl>
    {/if}
    <div class="actions">
      <button type="button" class="quiet" onclick={() => tips.setOn(false)}>Stop showing tips</button>
      <Button variant="primary" onclick={() => tips.dismiss(id)}>Got it</Button>
    </div>
  </aside>
{/if}

<style>
  .tip {
    padding: var(--space-3) var(--space-4);
    color: var(--text);
    background: var(--surface-2);
    border: 1px solid var(--accent);
    border-radius: var(--radius-card);
    margin-block-end: var(--space-3);
  }

  .tip.floating {
    position: absolute;
    inset-inline: 0;
    inset-block-end: var(--space-4);
    z-index: 5;
    width: min(420px, calc(100% - 24px));
    margin: 0 auto;
    box-shadow: var(--shadow);
    /* Let drawing continue underneath. Only the buttons take clicks. */
    pointer-events: none;
  }

  .tip.floating :global(button) {
    pointer-events: auto;
  }

  .head {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    color: var(--accent-text);
  }

  .body {
    margin: var(--space-1) 0 0;
    color: var(--text-2);
  }

  ul {
    margin: var(--space-2) 0 0;
    padding-inline-start: var(--space-4);
    color: var(--text-2);
    font-size: var(--text-small);
  }

  li + li {
    margin-block-start: 2px;
  }

  dl {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1) var(--space-3);
    margin: var(--space-2) 0 0;
    font-size: var(--text-small);
  }

  dl div {
    display: flex;
    gap: var(--space-1);
    align-items: baseline;
  }

  dt {
    padding: 0 6px;
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: var(--radius-chip);
  }

  dd {
    margin: 0;
    color: var(--text-2);
  }

  .actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    margin-block-start: var(--space-3);
  }

  .quiet {
    padding: 0;
    font-size: var(--text-small);
    color: var(--text-2);
    text-decoration: underline;
    background: none;
    border: 0;
    cursor: pointer;
  }
</style>
