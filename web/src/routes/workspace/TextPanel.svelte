<script lang="ts">
  import { Plus, Trash } from '@lucide/svelte';
  import { tick } from 'svelte';
  import type { Workspace } from '../../lib/state/workspace.svelte';
  import Button from '../../lib/ui/Button.svelte';
  import IconButton from '../../lib/ui/IconButton.svelte';

  const LIMIT = 5000;

  let { ws }: { ws: Workspace } = $props();

  // Re-read the shapes whenever the model changes, so undo and remote edits show up here.
  const entries = $derived((void ws.modelTick, ws.textShapes()));
  let box: HTMLDivElement | undefined = $state();

  async function add(): Promise<void> {
    ws.addText();
    await tick();
    box?.querySelector<HTMLTextAreaElement>('li:last-child textarea')?.focus();
  }
</script>

<div class="panel" bind:this={box}>
  {#if !ws.currentId}
    <p class="hint">Open an image to write about it.</p>
  {:else}
    <p class="hint">
      Write what the picture shows, or any text that goes with it. Add as many entries as you like,
      for example one caption per line of a dataset.
    </p>
    <ul>
      {#each entries as entry, i (entry.id)}
        {@const text = ws.textOf(entry)}
        <li>
          <label>
            <span class="row">
              <span>Text {i + 1}</span>
              <span class="count mono" class:near={text.length > LIMIT * 0.9}>{text.length.toLocaleString()} / {LIMIT.toLocaleString()}</span>
            </span>
            <textarea
              rows="3"
              maxlength={LIMIT}
              value={text}
              disabled={ws.readOnly}
              onchange={(e) => ws.setText(entry.id, e.currentTarget.value)}
            ></textarea>
          </label>
          <div class="tools">
            <select
              aria-label="Label for text {i + 1}"
              value={entry.classId}
              disabled={ws.readOnly}
              onchange={(e) => ws.setTextLabel(entry.id, e.currentTarget.value)}
            >
              <option value="">No label</option>
              {#each ws.classes as cls (cls.id)}<option value={cls.id}>{cls.name}</option>{/each}
            </select>
            <IconButton label="Delete text {i + 1}" onclick={() => ws.removeText(entry.id)}><Trash size={16} /></IconButton>
          </div>
        </li>
      {/each}
    </ul>
    {#if !ws.readOnly}
      <Button onclick={add}><Plus size={16} />Add text</Button>
    {/if}
  {/if}
</div>

<style>
  .panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding: var(--space-3);
  }

  .hint {
    margin: 0;
    color: var(--text-2);
  }

  ul {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  label {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    font-weight: 500;
  }

  .row {
    display: flex;
    justify-content: space-between;
  }

  .count {
    font-weight: 400;
    font-size: var(--text-small);
    color: var(--text-3);
  }

  .count.near {
    color: var(--warning-text);
  }

  textarea {
    padding: var(--space-2) 10px;
    font: inherit;
    resize: vertical;
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
  }

  .tools {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
  }

  select {
    height: var(--h-button-sm);
    min-width: 0;
    padding-inline: var(--space-2);
    color: var(--text-2);
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
  }
</style>
