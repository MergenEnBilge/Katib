<script lang="ts">
  /**
   * The words of a document, with the labelled runs of characters marked in their class colours.
   *
   * Labelling is select-then-it-is-done: choose a class, select words, and the span appears. The
   * list underneath is there for the keyboard and for checking the work, and it is also what
   * makes every span reachable without a mouse.
   */
  import { Trash2 } from '@lucide/svelte';
  import type { Workspace } from '../../lib/state/workspace.svelte';
  import { segments, spanRange, trim } from '../../lib/text/spans';
  import { plural } from '../../lib/format';

  let { ws }: { ws: Workspace } = $props();

  let sheet: HTMLElement | null = $state(null);
  let words = $derived(ws.documentText ?? '');
  let spans = $derived(ws.spans());
  let parts = $derived(segments(words.length, spans));
  let selected = $derived(ws.selectedIds);
  const activeClass = $derived(ws.classes.find((c) => c.id === ws.activeClassId) ?? null);

  function colorOf(classId: string): string {
    return ws.styles.get(classId)?.color ?? 'var(--accent)';
  }

  function nameOf(classId: string): string {
    return ws.styles.get(classId)?.name ?? 'no class';
  }

  /** Where in the whole document a point inside the rendered words sits. */
  function offsetAt(node: Node | null, offset: number): number | null {
    if (!node) return null;
    let element: Element | null =
      node.nodeType === Node.TEXT_NODE ? node.parentElement : (node as Element);
    while (element && !(element instanceof HTMLElement && element.dataset.start)) {
      element = element.parentElement;
    }
    if (!(element instanceof HTMLElement) || !element.dataset.start) return null;
    const base = Number(element.dataset.start);
    if (node.nodeType === Node.TEXT_NODE) return base + offset;
    // The selection landed on the element rather than inside its words, so use its edges.
    return offset > 0 ? base + (element.textContent?.length ?? 0) : base;
  }

  function labelSelection(): void {
    const selection = window.getSelection();
    if (!selection || selection.isCollapsed || ws.readOnly) return;
    // Only a selection in these words means anything here.
    if (!sheet || !selection.anchorNode || !sheet.contains(selection.anchorNode)) return;
    const from = offsetAt(selection.anchorNode, selection.anchorOffset);
    const to = offsetAt(selection.focusNode, selection.focusOffset);
    if (from === null || to === null) return;
    const range = trim(words, Math.min(from, to), Math.max(from, to));
    if (!range) return;
    if (ws.addSpan(range.start, range.end)) selection.removeAllRanges();
  }

  function onkeydown(event: KeyboardEvent): void {
    if (event.key !== 'Delete' && event.key !== 'Backspace') return;
    const [first] = [...selected];
    if (!first || ws.readOnly) return;
    event.preventDefault();
    ws.removeSpan(first);
  }
</script>

<svelte:window {onkeydown} onmouseup={labelSelection} ontouchend={labelSelection} />

<div class="document">
  {#if ws.documentText === null}
    <p class="waiting">Opening the document…</p>
  {:else}
    <div class="sheet">
      <!-- The words themselves. Marks are not focusable: the list below is the keyboard way in. -->
      <p class="words" bind:this={sheet} data-testid="document-words">
        {#each parts as part (part.start)}
          {#if part.spans.length === 0}
            <span data-start={part.start}>{words.slice(part.start, part.end)}</span>
          {:else if part.top}
            {@const top = part.top}
            <mark
              data-start={part.start}
              class:picked={selected.has(top.id)}
              style="--mark: {colorOf(top.classId)}"
              title={part.spans.map((s) => nameOf(s.classId)).join(', ')}
              onclick={() => ws.selectSpan(top.id)}
              onkeydown={(e) => e.key === 'Enter' && ws.selectSpan(top.id)}
              role="presentation">{words.slice(part.start, part.end)}</mark
            >
          {/if}
        {/each}
      </p>

      {#if !ws.readOnly}
        <p class="hint">
          {#if activeClass}
            Select words to label them <strong>{activeClass.name}</strong>. Press 1 to 9 to change
            class, or Delete to remove the one you picked.
          {:else}
            Choose a class on the right, then select words to label them.
          {/if}
        </p>
      {/if}

      <section class="list" aria-label="Labelled spans">
        <h3>{plural(spans.length, 'span')}</h3>
        {#if spans.length === 0}
          <p class="hint">Nothing labelled in this document yet.</p>
        {:else}
          <ul>
            {#each spans as span (span.id)}
              {@const range = spanRange(span)}
              <li class:picked={selected.has(span.id)}>
                <button type="button" class="pick" onclick={() => ws.selectSpan(span.id)}>
                  <span class="swatch" style="background: {colorOf(span.classId)}"></span>
                  <span class="what">{nameOf(span.classId)}</span>
                  <span class="quote">{words.slice(range.start, range.end)}</span>
                </button>
                {#if !ws.readOnly}
                  <button
                    type="button"
                    class="drop"
                    aria-label="Remove this {nameOf(span.classId)} span"
                    onclick={() => ws.removeSpan(span.id)}><Trash2 size={14} /></button
                  >
                {/if}
              </li>
            {/each}
          </ul>
        {/if}
      </section>
    </div>
  {/if}
</div>

<style>
  .document {
    position: absolute;
    inset: 0;
    overflow: auto;
    background: var(--surface-1);
  }
  .sheet {
    max-width: 46rem;
    margin: 0 auto;
    padding: 2rem 1.25rem 4rem;
  }
  .words {
    font-size: 1.05rem;
    line-height: 2;
    white-space: pre-wrap;
    overflow-wrap: break-word;
    color: var(--text);
  }
  mark {
    background: color-mix(in srgb, var(--mark) 26%, transparent);
    border-bottom: 2px solid var(--mark);
    border-radius: 3px;
    color: inherit;
    padding: 0.1em 0;
    cursor: pointer;
  }
  mark.picked {
    background: color-mix(in srgb, var(--mark) 52%, transparent);
    outline: 2px solid var(--mark);
  }
  .hint {
    color: var(--text-2);
    font-size: 0.9rem;
    margin-top: 1.25rem;
  }
  .list {
    margin-top: 2rem;
    border-top: 1px solid var(--border);
    padding-top: 1rem;
  }
  .list h3 {
    font-size: 0.95rem;
    margin-bottom: 0.5rem;
  }
  ul {
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }
  li {
    display: flex;
    align-items: center;
    gap: 0.25rem;
    border-radius: 8px;
  }
  li.picked {
    background: var(--surface-2);
  }
  .pick {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.4rem 0.5rem;
    background: none;
    border: 0;
    color: var(--text);
    font: inherit;
    text-align: left;
    cursor: pointer;
    min-width: 0;
  }
  .swatch {
    width: 0.75rem;
    height: 0.75rem;
    border-radius: 3px;
    flex: none;
  }
  .what {
    font-weight: 600;
    flex: none;
  }
  .quote {
    color: var(--text-2);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .drop {
    background: none;
    border: 0;
    color: var(--text-3);
    padding: 0.4rem;
    border-radius: 6px;
    cursor: pointer;
    flex: none;
  }
  .drop:hover {
    color: var(--danger);
    background: var(--surface-2);
  }
  .waiting {
    padding: 2rem;
    color: var(--text-2);
  }
</style>
