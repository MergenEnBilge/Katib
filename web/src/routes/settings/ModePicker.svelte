<script lang="ts">
  import { Check, Globe, Laptop, Users } from '@lucide/svelte';
  import { activeMode, MODES } from './modes';

  let {
    current,
    onpick,
  }: { current: (key: string) => unknown; onpick: (values: Record<string, unknown>) => void } =
    $props();

  const active = $derived(activeMode(current));
</script>

<div class="modes" role="group" aria-label="How you use Katib">
  {#each MODES as mode (mode.id)}
    <button
      type="button"
      class="mode"
      class:active={active === mode.id}
      aria-pressed={active === mode.id}
      onclick={() => onpick(mode.values)}
    >
      <span class="top">
        {#if mode.id === 'alone'}<Laptop size={18} />{:else if mode.id === 'team'}<Users size={18} />{:else}<Globe size={18} />{/if}
        <strong>{mode.label}</strong>
        {#if active === mode.id}<span class="tick"><Check size={14} strokeWidth={3} /></span>{/if}
      </span>
      <span class="hint">{mode.hint}</span>
    </button>
  {/each}
</div>

{#if active === null}
  <p class="custom">These do not match your settings. That is fine, yours are below.</p>
{/if}

<style>
  .modes {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: var(--space-2);
    margin-block-end: var(--space-4);
  }

  .mode {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    padding: var(--space-3);
    font: inherit;
    text-align: start;
    color: var(--text);
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: var(--radius-card);
    cursor: pointer;
  }

  .mode:hover {
    border-color: var(--border-strong);
  }

  .mode.active {
    background: var(--accent-muted);
    border-color: var(--accent-text);
  }

  .top {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .tick {
    display: inline-flex;
    margin-inline-start: auto;
    color: var(--accent-text);
  }

  .hint {
    font-size: var(--text-small);
    color: var(--text-2);
  }

  .custom {
    margin: calc(-1 * var(--space-3)) 0 var(--space-4);
    font-size: var(--text-small);
    color: var(--text-2);
  }
</style>
