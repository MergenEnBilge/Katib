<script lang="ts">
  import { WifiOff } from '@lucide/svelte';
  import { connection } from '../state/connection.svelte';
  import { toasts } from '../state/toast.svelte';

  // Saying when it is back matters as much as saying it is gone: otherwise nobody knows whether
  // to keep waiting or to go and restart it.
  $effect(() => {
    function back(): void {
      toasts.show('Connected to Katib again.');
    }
    window.addEventListener('katib:reconnected', back);
    return () => window.removeEventListener('katib:reconnected', back);
  });
</script>

{#if connection.lost}
  <div class="banner" role="status">
    <WifiOff size={16} aria-hidden="true" />
    <p>
      <strong>Katib's server is not answering.</strong>
      It may have been stopped, or be restarting. Anything you change here is kept and saved once it
      is back, and this page reconnects by itself.
    </p>
    <button type="button" disabled={connection.checking} onclick={() => connection.retry()}>
      {connection.checking ? 'Checking...' : 'Try now'}
    </button>
  </div>
{/if}

<style>
  .banner {
    position: fixed;
    inset: var(--safe-top, 0) 0 auto;
    z-index: 1000;
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-2) var(--space-4);
    color: var(--text);
    background: var(--surface-2);
    border-block-end: 2px solid var(--warning);
    box-shadow: var(--shadow);
    font-size: var(--text-small);
  }

  p {
    flex: 1;
    margin: 0;
  }

  button {
    flex: none;
    height: var(--h-button-sm);
    padding-inline: var(--space-3);
    color: var(--text);
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
    cursor: pointer;
  }
</style>
