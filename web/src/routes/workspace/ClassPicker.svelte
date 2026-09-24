<script lang="ts">
  import type { Workspace } from '../../lib/state/workspace.svelte';

  let { ws, onclose }: { ws: Workspace; onclose: () => void } = $props();

  let query = $state('');
  let index = $state(0);
  let input: HTMLInputElement | undefined = $state();

  const matches = $derived(
    ws.classes.filter((c) => c.name.toLowerCase().includes(query.trim().toLowerCase())),
  );

  $effect(() => {
    input?.focus();
  });

  $effect(() => {
    void query;
    index = 0;
  });

  function pick(id: string): void {
    ws.chooseClass(id);
    onclose();
  }

  function keydown(e: KeyboardEvent): void {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      index = Math.min(index + 1, matches.length - 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      index = Math.max(index - 1, 0);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      const match = matches[index];
      if (match) pick(match.id);
    } else if (e.key === 'Escape') {
      e.stopPropagation();
      onclose();
    }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="scrim" onclick={(e) => e.target === e.currentTarget && onclose()}>
  <div class="picker" role="dialog" aria-label="Choose a class">
    <input
      bind:this={input}
      bind:value={query}
      placeholder="Search classes"
      aria-label="Search classes"
      role="combobox"
      aria-expanded="true"
      aria-controls="class-picker-list"
      onkeydown={keydown}
    />
    <ul id="class-picker-list" role="listbox">
      {#each matches as cls, i (cls.id)}
        <li role="option" aria-selected={i === index}>
          <button type="button" class:active={i === index} onclick={() => pick(cls.id)}>
            <span class="swatch" style:background={cls.color}></span>{cls.name}
          </button>
        </li>
      {:else}
        <li class="none">No class matches.</li>
      {/each}
    </ul>
  </div>
</div>

<style>
  .scrim {
    position: fixed;
    inset: 0;
    z-index: var(--z-menu-backdrop);
  }

  .picker {
    position: absolute;
    inset-block-start: 20vh;
    inset-inline-start: 50%;
    transform: translateX(-50%);
    z-index: var(--z-menu);
    width: 260px;
    padding: var(--space-1);
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--radius-card);
    box-shadow: var(--shadow);
  }

  input {
    width: 100%;
    height: var(--h-button);
    padding-inline: var(--space-2);
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
  }

  ul {
    max-height: 260px;
    margin: var(--space-1) 0 0;
    padding: 0;
    overflow-y: auto;
    list-style: none;
  }

  button {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    height: var(--h-button);
    padding-inline: var(--space-2);
    text-align: start;
    background: transparent;
    border: 0;
    border-radius: var(--radius-control);
    cursor: pointer;
  }

  button:hover,
  button.active {
    background: var(--accent-muted);
  }

  .swatch {
    width: 10px;
    height: 10px;
    border-radius: var(--radius-swatch);
  }

  .none {
    padding: var(--space-2);
    color: var(--text-2);
  }
</style>
