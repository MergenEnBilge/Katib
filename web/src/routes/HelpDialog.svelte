<script lang="ts">
  import { BookOpen, Compass, Keyboard, Lightbulb, MessageCircleQuestion, Route } from '@lucide/svelte';
  import type { Component } from 'svelte';
  import { tips } from '../lib/state/tips.svelte';
  import Modal from '../lib/ui/Modal.svelte';

  const GUIDE = 'https://github.com/MergenEnBilge/Katib/tree/main/docs';
  const ISSUES = 'https://github.com/MergenEnBilge/Katib/issues';

  let {
    onclose,
    ontour,
    tours = [],
    onsample,
    onshortcuts,
  }: {
    onclose: () => void;
    ontour?: () => void;
    /** Tours of other screens, so someone can learn a part before they get there. */
    tours?: { label: string; note: string; run: () => void }[];
    onsample?: () => void;
    onshortcuts?: () => void;
  } = $props();

  interface Item {
    icon: Component;
    title: string;
    note: string;
    run?: () => void;
    href?: string;
  }

  const items = $derived<Item[]>(
    [
      ontour && { icon: Compass, title: 'Take the tour', note: 'A one-minute walk around this workspace.', run: ontour },
      ...tours.map((t) => ({ icon: Route, title: t.label, note: t.note, run: t.run })),
      onsample && {
        icon: Lightbulb,
        title: 'Practice with sample pictures',
        note: 'Make a small project with ready-made pictures and try every tool.',
        run: onsample,
      },
      onshortcuts && { icon: Keyboard, title: 'Keyboard shortcuts', note: 'Everything you can do without the mouse.', run: onshortcuts },
      { icon: BookOpen, title: 'Read the guide', note: 'Step-by-step help for every feature.', href: GUIDE },
      { icon: MessageCircleQuestion, title: 'Ask a question or report a problem', note: 'Opens the project page in a new tab.', href: ISSUES },
    ].filter(Boolean) as Item[],
  );
</script>

<Modal title="Help" description="New here? Start with the tour, or practice on pictures we made for you." {onclose}>
  <ul>
    {#each items as item (item.title)}
      <li>
        {#if item.href}
          <a href={item.href} target="_blank" rel="noopener noreferrer">
            <item.icon size={18} />
            <span><strong>{item.title}</strong><small>{item.note}</small></span>
          </a>
        {:else}
          <button type="button" onclick={item.run}>
            <item.icon size={18} />
            <span><strong>{item.title}</strong><small>{item.note}</small></span>
          </button>
        {/if}
      </li>
    {/each}
  </ul>

  <div class="tips">
    <label class="switch">
      <input type="checkbox" checked={tips.on} onchange={(e) => tips.setOn(e.currentTarget.checked)} />
      Show a short tip the first time I use a tool or window
    </label>
    <button type="button" class="again" onclick={() => tips.reset()}>Show every tip again</button>
  </div>
</Modal>

<style>
  ul {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    margin: 0;
    padding: 0;
    list-style: none;
  }

  a,
  button {
    display: flex;
    gap: var(--space-3);
    align-items: flex-start;
    width: 100%;
    padding: var(--space-3);
    color: var(--text);
    text-align: start;
    text-decoration: none;
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: var(--radius-group);
    cursor: pointer;
  }

  a:hover,
  button:hover {
    background: var(--accent-muted);
    border-color: var(--accent);
  }

  .tips {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    margin-block-start: var(--space-4);
    padding-block-start: var(--space-3);
    border-block-start: 1px solid var(--border);
    font-size: var(--text-small);
    color: var(--text-2);
  }

  .switch {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .again {
    align-self: flex-start;
    padding: 0;
    color: var(--text-2);
    text-decoration: underline;
    background: none;
    border: 0;
    cursor: pointer;
  }

  span {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  small {
    color: var(--text-2);
    font-size: var(--text-small);
  }
</style>
