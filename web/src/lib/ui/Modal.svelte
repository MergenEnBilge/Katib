<script lang="ts">
  import type { Snippet } from 'svelte';

  let {
    title,
    description,
    width = 460,
    onclose,
    children,
    footer,
  }: {
    title: string;
    description?: string;
    width?: number;
    onclose: () => void;
    children: Snippet;
    footer?: Snippet;
  } = $props();

  let dialog: HTMLDivElement | undefined = $state();

  $effect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const first = dialog?.querySelector<HTMLElement>('input, select, textarea, button:not([data-close])');
    first?.focus();
    return () => previous?.focus();
  });

  function keydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.stopPropagation();
      onclose();
      return;
    }
    if (event.key !== 'Tab' || !dialog) return;
    const items = [
      ...dialog.querySelectorAll<HTMLElement>('input, select, textarea, button, [href]'),
    ].filter((el) => !el.hasAttribute('disabled'));
    const first = items[0];
    const last = items[items.length - 1];
    if (!first || !last) return;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
<div class="scrim" onclick={(e) => e.target === e.currentTarget && onclose()}>
  <div
    class="modal"
    role="dialog"
    aria-modal="true"
    aria-label={title}
    style:width="{width}px"
    bind:this={dialog}
    onkeydown={keydown}
    tabindex="-1"
  >
    <header>
      <h2>{title}</h2>
      {#if description}<p>{description}</p>{/if}
    </header>
    <div class="body">{@render children()}</div>
    {#if footer}<footer>{@render footer()}</footer>{/if}
  </div>
</div>

<style>
  .scrim {
    position: fixed;
    inset: 0;
    z-index: var(--z-modal);
    display: grid;
    place-items: center;
    background: var(--scrim);
  }

  .modal {
    max-width: calc(100vw - 2 * var(--space-6));
    max-height: calc(100vh - 2 * var(--space-6));
    display: flex;
    flex-direction: column;
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--radius-card);
    box-shadow: var(--shadow);
  }

  header {
    padding: 20px 20px var(--space-2);
  }

  h2 {
    margin: 0;
    font-size: var(--text-heading);
    font-weight: 500;
  }

  header p {
    margin: var(--space-1) 0 0;
    color: var(--text-2);
    font-size: var(--text-small);
  }

  .body {
    padding: var(--space-3) 20px 20px;
    overflow: auto;
  }

  footer {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-2);
    padding: var(--space-3) 20px;
    border-block-start: 1px solid var(--border);
  }
</style>
