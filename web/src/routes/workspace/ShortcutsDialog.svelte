<script lang="ts">
  import { SHORTCUT_LIST } from '../../lib/shortcuts/keys';
  import Button from '../../lib/ui/Button.svelte';
  import Modal from '../../lib/ui/Modal.svelte';

  let { onclose }: { onclose: () => void } = $props();

  const groups = [...new Set(SHORTCUT_LIST.map((s) => s.group))];
</script>

<Modal title="Keyboard shortcuts" width={520} {onclose}>
  {#each groups as group (group)}
    <p class="group">{group}</p>
    <dl>
      {#each SHORTCUT_LIST.filter((s) => s.group === group) as s (s.keys)}
        <dt><kbd>{s.keys}</kbd></dt>
        <dd>{s.action}</dd>
      {/each}
    </dl>
  {/each}
  {#snippet footer()}
    <Button variant="primary" onclick={onclose}>Close</Button>
  {/snippet}
</Modal>

<style>
  .group {
    margin: var(--space-3) 0 var(--space-1);
    font-size: var(--text-overline);
    font-weight: 500;
    color: var(--text-3);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  dl {
    display: grid;
    grid-template-columns: 150px 1fr;
    gap: var(--space-1) var(--space-3);
    margin: 0;
  }

  dt,
  dd {
    margin: 0;
  }

  kbd {
    font-family: var(--font-mono);
    font-size: var(--text-overline);
    color: var(--text-2);
    padding: 1px 6px;
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-chip);
  }
</style>
