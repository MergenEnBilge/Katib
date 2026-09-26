<script lang="ts">
  // Katib cannot always work out the address people use to reach it. In Docker the only address it
  // can see is the container's, which nothing outside Docker can reach. Rather than shrug, it asks
  // once and remembers the answer, which is what every QR code and invite link is built from.
  import { api, ApiError } from '../../lib/api/client';
  import Button from '../../lib/ui/Button.svelte';
  import TextField from '../../lib/ui/TextField.svelte';

  let { port, onsaved }: { port: number; onsaved: () => void } = $props();

  let address = $state('');
  let error = $state('');
  let busy = $state(false);

  async function save(): Promise<void> {
    if (!address.trim()) {
      error = 'Type the address, such as 192.168.1.20:' + port + '.';
      return;
    }
    busy = true;
    error = '';
    try {
      await api.settings.save({ 'server.public_url': address.trim() });
      onsaved();
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not save that address.';
    } finally {
      busy = false;
    }
  }
</script>

<div class="ask">
  <p class="line"><strong>What address do people type to reach this computer?</strong></p>
  <p class="hint">
    Katib is open to the network but cannot see this computer's address from where it is running.
    On Windows run <code>ipconfig</code>, on a Mac or Linux <code>hostname -I</code>, and use the
    address that starts with 192.168, 10. or 172. Katib saves it and builds every code and invite
    link from it.
  </p>
  <div class="row">
    <TextField label="Address" placeholder="192.168.1.20:{port}" bind:value={address} {error} onenter={save} />
    <Button variant="primary" disabled={busy} onclick={save}>Save</Button>
  </div>
</div>

<style>
  .ask {
    padding: var(--space-3);
    background: var(--surface-2);
    border-radius: var(--radius-card);
  }

  .line {
    margin: 0 0 var(--space-1);
  }

  .hint {
    margin: 0 0 var(--space-3);
    max-width: 62ch;
    color: var(--text-2);
    font-size: var(--text-small);
  }

  code {
    font-family: var(--font-mono);
  }

  .row {
    display: flex;
    gap: var(--space-2);
    align-items: flex-end;
  }

  .row :global(.field) {
    flex: 1;
  }
</style>
