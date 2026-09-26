<script lang="ts">
  import { api, ApiError } from '../../lib/api/client';
  import type { ShareInfo } from '../../lib/api/types';
  import Callout from '../../lib/ui/Callout.svelte';
  import AddressForm from './AddressForm.svelte';

  let info = $state<ShareInfo | null>(null);
  let error = $state('');

  function load(): void {
    api.share
      .get()
      .then((s) => (info = s))
      .catch((err) => (error = err instanceof ApiError ? err.message : 'Could not check how Katib is shared.'));
  }

  $effect(load);
</script>

<section class="share" aria-labelledby="share-title">
  <h3 id="share-title">How people reach Katib</h3>
  {#if error}
    <Callout tone="danger">{error}</Callout>
  {:else if !info}
    <p class="quiet">Checking...</p>
  {:else if info.needs_address}
    <AddressForm port={info.port} onsaved={load} />
  {:else if !info.reachable}
    <p class="quiet">
      Katib only answers on this computer right now. To let others in, choose accounts and
      &ldquo;Everyone on my network&rdquo; above, save, and restart.
    </p>
  {:else}
    {#if !info.accounts}
      <Callout tone="danger">Anyone who can reach this address can use Katib. Turn accounts on.</Callout>
    {/if}
    <ul>
      {#each info.urls as url (url)}
        <li>
          <span class="mono">{url}</span>
          <img src={api.share.qrUrl(url)} alt="QR code for {url}" width="120" height="120" />
        </li>
      {/each}
    </ul>
    {#if !info.secure}
      <p class="quiet">
        This address uses plain HTTP. That is fine on a network you trust. For the internet, put HTTPS
        in front of Katib. The guide to putting Katib online shows how.
      </p>
    {/if}
  {/if}
</section>

<style>
  .share {
    margin-block-start: var(--space-6);
  }

  h3 {
    margin: 0 0 var(--space-2);
    font-size: var(--text-heading);
  }

  .quiet {
    margin: 0;
    max-width: 68ch;
    color: var(--text-2);
  }

  ul {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-4);
    margin: var(--space-3) 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  img {
    background: #fff;
    border: 1px solid var(--border);
    border-radius: var(--radius-control);
  }
</style>
