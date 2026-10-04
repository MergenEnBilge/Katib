<script lang="ts">
  /**
   * The buckets this server can read pictures from.
   *
   * Katib tries the details before it keeps them, and says how many objects it could see, so a
   * wrong key or region is caught here rather than when someone tries to label something.
   */
  import { Cloud, Trash2 } from '@lucide/svelte';
  import { api, ApiError } from '../../lib/api/client';
  import type { CloudSource } from '../../lib/api/types';
  import Button from '../../lib/ui/Button.svelte';
  import Callout from '../../lib/ui/Callout.svelte';
  import TextField from '../../lib/ui/TextField.svelte';

  let sources = $state<CloudSource[]>([]);
  let adding = $state(false);
  let busy = $state(false);
  let error = $state('');
  let done = $state('');

  let name = $state('');
  let provider = $state<'s3' | 'azure'>('s3');
  let bucket = $state('');
  let accessKey = $state('');
  let secret = $state('');
  let region = $state('us-east-1');
  let endpoint = $state('');
  let prefix = $state('');

  const azure = $derived(provider === 'azure');

  async function load(): Promise<void> {
    try {
      sources = await api.cloud.list();
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not read the list of buckets.';
    }
  }

  $effect(() => {
    void load();
  });

  function startOver(): void {
    name = '';
    bucket = '';
    accessKey = '';
    secret = '';
    region = 'us-east-1';
    endpoint = '';
    prefix = '';
    provider = 's3';
  }

  async function save(): Promise<void> {
    busy = true;
    error = '';
    done = '';
    try {
      const result = await api.cloud.save({
        name: name.trim(),
        provider,
        bucket: bucket.trim(),
        access_key: accessKey.trim(),
        secret: secret.trim(),
        region: region.trim(),
        endpoint: endpoint.trim(),
        prefix: prefix.trim(),
      });
      done = `Saved. Katib can see ${result.objects} object${result.objects === 1 ? '' : 's'} there.`;
      adding = false;
      startOver();
      await load();
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not save that bucket.';
    } finally {
      busy = false;
    }
  }

  async function forget(source: CloudSource): Promise<void> {
    if (
      !confirm(
        `Forget ${source.name}? Pictures already in a project cannot be opened until it is set up again.`,
      )
    ) {
      return;
    }
    busy = true;
    error = '';
    try {
      await api.cloud.forget(source.name);
      await load();
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not forget that bucket.';
    } finally {
      busy = false;
    }
  }
</script>

<section class="cloud">
  <h3>Buckets</h3>
  <p class="note">
    Read pictures straight from Amazon S3, Cloudflare R2, Backblaze B2, MinIO, Google Cloud Storage
    or Azure. The pictures stay where they are: Katib keeps their thumbnails and fetches a picture
    when somebody opens it. Give it a key that can only read.
  </p>

  {#if sources.length > 0}
    <ul aria-label="Buckets">
      {#each sources as source (source.name)}
        <li>
          <Cloud size={16} />
          <span class="what">
            <strong>{source.name}</strong>
            <small class="mono">
              {source.provider === 'azure' ? 'Azure' : 'S3'} · {source.bucket}{source.prefix
                ? `/${source.prefix}`
                : ''}
            </small>
          </span>
          <button
            type="button"
            class="drop"
            aria-label="Forget {source.name}"
            disabled={busy}
            onclick={() => forget(source)}><Trash2 size={14} /></button
          >
        </li>
      {/each}
    </ul>
  {/if}

  {#if done}<Callout>{done}</Callout>{/if}
  {#if error}<Callout tone="danger">{error}</Callout>{/if}

  {#if adding}
    <div class="form">
      <TextField label="A name for this bucket" placeholder="photos" bind:value={name} />
      <label class="select">
        <span>Where it is</span>
        <select bind:value={provider}>
          <option value="s3">Amazon S3, R2, B2, MinIO or Google Cloud Storage</option>
          <option value="azure">Azure Blob Storage</option>
        </select>
      </label>
      <TextField
        label={azure ? 'Container' : 'Bucket'}
        placeholder={azure ? 'pictures' : 'my-bucket'}
        bind:value={bucket}
      />
      <TextField
        label={azure ? 'Storage account name' : 'Access key'}
        bind:value={accessKey}
        hint={azure ? 'The account the container belongs to.' : ''}
      />
      <TextField
        label={azure ? 'Account key' : 'Secret key'}
        bind:value={secret}
        hint="Kept on this server, in a file only Katib can read. It is never shown again."
      />
      {#if !azure}
        <TextField label="Region" placeholder="eu-west-1" bind:value={region} />
        <TextField
          label="Address, if it is not Amazon"
          placeholder="https://play.min.io"
          bind:value={endpoint}
          hint="For R2, B2, MinIO, or Google Cloud Storage at https://storage.googleapis.com."
        />
      {:else}
        <TextField
          label="Address, if it is not the usual one"
          placeholder="https://myaccount.blob.core.windows.net"
          bind:value={endpoint}
        />
      {/if}
      <TextField
        label="Only read names starting with"
        placeholder="datasets/street/"
        bind:value={prefix}
        hint="Leave this empty to read the whole bucket."
      />
      <div class="buttons">
        <Button onclick={() => ((adding = false), startOver())}>Cancel</Button>
        <Button
          variant="primary"
          loading={busy}
          disabled={!name.trim() || !bucket.trim() || !accessKey.trim() || !secret.trim()}
          onclick={save}>Check and save</Button
        >
      </div>
    </div>
  {:else}
    <div><Button onclick={() => (adding = true)}><Cloud size={16} />Add a bucket</Button></div>
  {/if}
</section>

<style>
  .cloud {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    padding-top: 1rem;
    border-top: 1px solid var(--border);
  }
  h3 {
    font-size: 1rem;
  }
  .note {
    color: var(--text-2);
    font-size: 0.9rem;
    max-width: 48rem;
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
    gap: 0.6rem;
    padding: 0.5rem 0.6rem;
    border: 1px solid var(--border);
    border-radius: 10px;
    color: var(--text-2);
  }
  .what {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-width: 0;
  }
  .what strong {
    color: var(--text);
  }
  .what small {
    color: var(--text-3);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .drop {
    background: none;
    border: 0;
    color: var(--text-3);
    padding: 0.35rem;
    border-radius: 6px;
    cursor: pointer;
  }
  .drop:hover {
    color: var(--danger);
    background: var(--surface-2);
  }
  .form {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    max-width: 32rem;
  }
  .select {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    font-size: 0.9rem;
  }
  .select select {
    padding: 0.5rem;
    border-radius: 8px;
    border: 1px solid var(--border);
    background: var(--surface-1);
    color: var(--text);
  }
  .buttons {
    display: flex;
    gap: 0.5rem;
    justify-content: flex-end;
  }
</style>
