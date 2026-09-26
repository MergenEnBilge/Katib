<script lang="ts">
  // Anyone handed a password by an administrator should be able to pick their own, and Settings
  // is not the place for it: on a shared server only administrators can open that page.
  import { api, ApiError } from '../lib/api/client';
  import { toasts } from '../lib/state/toast.svelte';
  import Button from '../lib/ui/Button.svelte';
  import Callout from '../lib/ui/Callout.svelte';
  import Modal from '../lib/ui/Modal.svelte';

  let { onclose }: { onclose: () => void } = $props();

  let current = $state('');
  let next = $state('');
  let again = $state('');
  let error = $state('');
  let busy = $state(false);

  async function save(): Promise<void> {
    if (next !== again) {
      error = 'The two new passwords are not the same.';
      return;
    }
    busy = true;
    error = '';
    try {
      await api.auth.changePassword(current, next);
      toasts.show('Password changed. Your other devices have been signed out.');
      onclose();
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not change the password.';
    } finally {
      busy = false;
    }
  }
</script>

<Modal
  title="Change your password"
  description="Your other devices are signed out, so a borrowed laptop stops being a way in."
  width={420}
  {onclose}
>
  {#if error}<Callout tone="danger">{error}</Callout>{/if}
  <div class="fields">
    <label>
      <span>Current password</span>
      <input type="password" autocomplete="current-password" bind:value={current} />
    </label>
    <label>
      <span>New password</span>
      <input type="password" autocomplete="new-password" bind:value={next} />
    </label>
    <label>
      <span>New password again</span>
      <input
        type="password"
        autocomplete="new-password"
        bind:value={again}
        onkeydown={(e) => e.key === 'Enter' && save()}
      />
    </label>
  </div>

  {#snippet footer()}
    <Button onclick={onclose}>Cancel</Button>
    <Button variant="primary" loading={busy} onclick={save}>Change it</Button>
  {/snippet}
</Modal>

<style>
  .fields {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  label {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  span {
    font-weight: 500;
  }

  input {
    height: var(--h-input);
    padding-inline: var(--space-2);
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
  }
</style>
