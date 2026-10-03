<script lang="ts">
  import { api, ApiError } from '../../lib/api/client';
  import { formatBytes, plural } from '../../lib/format';
  import Button from '../../lib/ui/Button.svelte';
  import Callout from '../../lib/ui/Callout.svelte';
  import Modal from '../../lib/ui/Modal.svelte';
  import TextField from '../../lib/ui/TextField.svelte';

  let preview = $state<{ files: number; bytes: number } | null>(null);
  let confirming = $state(false);
  let typed = $state('');
  let busy = $state(false);
  let error = $state('');
  let waiting = $state(false);
  /** Shown on the page, not in the window: by then the window has closed. */
  let afterwards = $state('');
  let previewError = $state('');

  $effect(() => {
    api.settings
      .factoryResetPreview()
      .then((p) => (preview = p))
      .catch((err: unknown) => {
        previewError = err instanceof ApiError ? err.message : 'Could not count what is there.';
      });
  });

  function open(): void {
    typed = '';
    error = '';
    confirming = true;
  }

  async function waitForFreshStart(): Promise<void> {
    waiting = true;
    for (let i = 0; i < 60; i++) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      try {
        await fetch('/api/v1/health', { mode: 'no-cors', cache: 'no-store' });
        location.assign('/');
        return;
      } catch {
        // Not back yet.
      }
    }
    waiting = false;
    afterwards =
      'Katib has not come back after a minute. Start it again by hand; if it will not start, its ' +
      'log (in the logs folder of the data folder) says why.';
  }

  async function run(): Promise<void> {
    busy = true;
    error = '';
    try {
      await api.settings.factoryReset(typed);
      confirming = false;
      await waitForFreshStart();
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not reset Katib.';
    } finally {
      busy = false;
    }
  }
</script>

<h3>Danger zone</h3>
<p class="note">
  Delete every project, uploaded picture and setting, and start over as if Katib were freshly
  installed. Pictures in a folder you only connected are never touched, since they were never
  copied here in the first place.
  {#if preview}This would remove {plural(preview.files, 'file')} ({formatBytes(preview.bytes)}).{/if}
</p>
{#if previewError}<Callout tone="danger">{previewError}</Callout>{/if}
<div><Button variant="danger" onclick={open}>Reset everything…</Button></div>

{#if confirming}
  <Modal title="Reset everything?" onclose={() => (confirming = false)}>
    <p>
      This deletes every project, class and label, every picture you uploaded, and every saved
      setting. It cannot be undone — make a backup first if there is anything worth keeping.
    </p>
    <TextField label='Type "RESET" to confirm' bind:value={typed} />
    {#if error}<Callout tone="danger">{error}</Callout>{/if}
    {#snippet footer()}
      <Button onclick={() => (confirming = false)}>Cancel</Button>
      <Button
        variant="danger"
        loading={busy}
        disabled={typed.trim().toUpperCase() !== 'RESET'}
        onclick={run}>{busy ? 'Resetting...' : 'Reset everything'}</Button
      >
    {/snippet}
  </Modal>
{/if}

{#if waiting}
  <Callout>Katib is starting over fresh. This page will reload once it is back.</Callout>
{/if}
{#if afterwards}<Callout tone="danger">{afterwards}</Callout>{/if}

<style>
  h3 {
    margin: var(--space-5) 0 var(--space-1);
    font-size: var(--text-heading);
    color: var(--danger-text);
  }

  .note {
    margin: 0 0 var(--space-2);
    color: var(--text-2);
    max-width: 68ch;
  }
</style>
