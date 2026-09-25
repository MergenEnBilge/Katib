<script lang="ts">
  import { Copy, ExternalLink, Trash2 } from '@lucide/svelte';
  import { api, ApiError } from '../lib/api/client';
  import type { ShareInfo } from '../lib/api/types';
  import { cleanServerUrl, loadServers, saveServers, type SavedServer } from '../lib/state/servers';
  import { toasts } from '../lib/state/toast.svelte';
  import Button from '../lib/ui/Button.svelte';
  import Callout from '../lib/ui/Callout.svelte';
  import Modal from '../lib/ui/Modal.svelte';
  import TextField from '../lib/ui/TextField.svelte';

  let { onclose }: { onclose: () => void } = $props();

  let tab = $state<'share' | 'servers'>('share');
  let info = $state<ShareInfo | null>(null);
  let problem = $state('');
  let servers = $state<SavedServer[]>(loadServers());
  let name = $state('');
  let address = $state('');
  let addressError = $state('');

  $effect(() => {
    api.share
      .get()
      .then((i) => (info = i))
      .catch((err: unknown) => {
        problem = err instanceof ApiError ? err.message : 'Could not check how Katib is shared.';
      });
  });

  async function copy(text: string): Promise<void> {
    try {
      await navigator.clipboard.writeText(text);
      toasts.show('Address copied.');
    } catch {
      toasts.show('Copy the address from the box.');
    }
  }

  function add(): void {
    const url = cleanServerUrl(address);
    if (!url) {
      addressError = 'Enter an address such as 192.168.1.20:8420 or https://katib.example.com.';
      return;
    }
    addressError = '';
    servers = [...servers.filter((s) => s.url !== url), { name: name.trim() || new URL(url).host, url }];
    saveServers(servers);
    name = '';
    address = '';
  }

  function forget(url: string): void {
    servers = servers.filter((s) => s.url !== url);
    saveServers(servers);
  }
</script>

<Modal title="Workspaces" description="Let others reach this computer, or switch to another Katib server." width={560} {onclose}>
  <div class="tabs" role="tablist">
    {#each [['share', 'Share this computer'], ['servers', 'Other servers']] as const as [id, label] (id)}
      <button type="button" role="tab" aria-selected={tab === id} class:active={tab === id} onclick={() => (tab = id)}>{label}</button>
    {/each}
  </div>

  {#if tab === 'share'}
    {#if problem}
      <Callout tone="danger">{problem}</Callout>
    {:else if info === null}
      <div class="sk" aria-busy="true"></div>
    {:else if !info.reachable}
      <Callout>
        <p class="line"><strong>Katib is only open on this computer.</strong></p>
        <p class="line">To let a phone or a colleague in, stop Katib and start it again with:</p>
        <p class="line"><code>katib share</code></p>
        <p class="line">That turns on accounts and prints an address and a QR code. Open this page again for the same details.</p>
      </Callout>
    {:else}
      <p class="lead">On a phone or another computer on the same network, open one of these addresses{info.accounts ? '. People sign in with an account you invite.' : '.'}</p>
      {#each info.urls as url, i (url)}
        <div class="address">
          <div class="row">
            <input readonly value={url} aria-label="Address" onfocus={(e) => e.currentTarget.select()} />
            <Button onclick={() => copy(url)}><Copy size={16} />Copy</Button>
          </div>
          {#if i === 0}
            <img class="qr" src={api.share.qrUrl(url)} alt="QR code for {url}" width="176" height="176" />
            <p class="hint">Point a phone camera at the code.</p>
          {/if}
        </div>
      {/each}
      {#if !info.secure}
        <Callout>
          This address is not encrypted. That is fine at home or in an office you trust. Passwords and
          annotations can be read by others on the same network, and phones cannot install Katib as an app.
          To add HTTPS, see “Running it on a server with Docker” in the README.
        </Callout>
      {/if}
    {/if}
  {:else}
    <p class="lead">Katib servers you use often. Opening one takes you to its sign-in page.</p>
    {#if servers.length > 0}
      <ul class="servers" aria-label="Saved servers">
        {#each servers as s (s.url)}
          <li>
            <span class="who"><strong>{s.name}</strong><small>{s.url}</small></span>
            <a class="open" href={s.url}><ExternalLink size={14} />Open</a>
            <button type="button" class="x" aria-label="Forget {s.name}" onclick={() => forget(s.url)}><Trash2 size={14} /></button>
          </li>
        {/each}
      </ul>
    {/if}
    <div class="add">
      <TextField label="Name" placeholder="Design team" bind:value={name} />
      <TextField label="Address" placeholder="192.168.1.20:8420" bind:value={address} error={addressError} onenter={add} />
      <div><Button onclick={add}>Save server</Button></div>
    </div>
  {/if}

  {#snippet footer()}
    <Button variant="primary" onclick={onclose}>Done</Button>
  {/snippet}
</Modal>

<style>
  .tabs {
    display: flex;
    gap: var(--space-1);
    margin-block-end: var(--space-3);
    padding: 2px;
    width: fit-content;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius-group);
  }

  .tabs button {
    height: 28px;
    padding-inline: var(--space-3);
    color: var(--text-2);
    background: transparent;
    border: 0;
    border-radius: var(--radius-control);
    cursor: pointer;
  }

  .tabs button.active {
    color: var(--accent-text);
    background: var(--accent-muted);
  }

  .lead,
  .hint {
    margin: 0 0 var(--space-3);
    color: var(--text-2);
  }

  .hint {
    margin: var(--space-1) 0 0;
    font-size: var(--text-small);
  }

  .line {
    margin: 0 0 var(--space-1);
  }

  .address {
    margin-block-end: var(--space-3);
  }

  .row {
    display: flex;
    gap: var(--space-2);
  }

  input {
    flex: 1;
    min-width: 0;
    height: var(--h-button-sm);
    padding-inline: var(--space-2);
    font-family: var(--font-mono);
    font-size: var(--text-small);
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
  }

  .qr {
    display: block;
    margin-block-start: var(--space-3);
    background: #fff;
    border: 1px solid var(--border);
    border-radius: var(--radius-card);
  }

  .servers {
    margin: 0 0 var(--space-4);
    padding: 0;
    list-style: none;
  }

  .servers li {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding-block: var(--space-2);
    border-block-end: 1px solid var(--border);
  }

  .who {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: 0;
  }

  small {
    overflow: hidden;
    color: var(--text-2);
    text-overflow: ellipsis;
  }

  .open {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    color: var(--accent-text);
  }

  .x {
    display: grid;
    place-items: center;
    width: var(--h-icon-sm);
    height: var(--h-icon-sm);
    color: var(--text-2);
    background: transparent;
    border: 0;
    cursor: pointer;
  }

  .add {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .sk {
    height: 120px;
    background: var(--surface-1);
    border-radius: var(--radius-card);
  }
</style>
