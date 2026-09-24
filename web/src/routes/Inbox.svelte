<script lang="ts">
  import { Inbox as InboxIcon } from '@lucide/svelte';
  import { onMount } from 'svelte';
  import { api, ApiError } from '../lib/api/client';
  import type { Inbox } from '../lib/api/types';
  import { plural } from '../lib/format';
  import { router } from '../lib/state/router.svelte';
  import Button from '../lib/ui/Button.svelte';
  import Callout from '../lib/ui/Callout.svelte';
  import EmptyState from '../lib/ui/EmptyState.svelte';
  import StatusDot from '../lib/ui/StatusDot.svelte';

  let inbox = $state<Inbox | null>(null);
  let error = $state('');

  async function load(): Promise<void> {
    error = '';
    try {
      inbox = await api.work.inbox();
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not load your inbox.';
    }
  }

  onMount(() => void load());

  function open(event: MouseEvent, projectId: string, imageId: string): void {
    if (event.metaKey || event.ctrlKey || event.shiftKey) return;
    event.preventDefault();
    router.navigate(`/p/${projectId}?image=${imageId}`);
  }
</script>

<header class="head"><h1>Inbox</h1></header>

{#if error}
  <Callout tone="danger">
    {error}
    {#snippet action()}<Button onclick={load}>Try again</Button>{/snippet}
  </Callout>
{:else if inbox === null}
  <div class="sk" aria-busy="true"></div>
{:else if inbox.assigned.length === 0 && inbox.to_review.length === 0}
  <EmptyState
    title="Nothing waiting for you"
    description="Images assigned to you and images waiting for your review show up here, across every project."
  >
    {#snippet icon()}<InboxIcon size={20} />{/snippet}
  </EmptyState>
{:else}
  {#if inbox.assigned.length > 0}
    <section>
      <h2>Assigned to you <span class="n mono">{inbox.assigned.length}</span></h2>
      <ul>
        {#each inbox.assigned as item (item.image_id)}
          <li>
            <a
              href="/p/{item.project_id}?image={item.image_id}"
              onclick={(e) => open(e, item.project_id, item.image_id)}
            >
              <StatusDot status={item.status} />
              <span class="file mono">{item.filename}</span>
              <span class="proj">{item.project_name}</span>
              {#if item.status === 'rejected'}<span class="tag">Sent back for changes</span>{/if}
            </a>
          </li>
        {/each}
      </ul>
    </section>
  {/if}
  {#if inbox.to_review.length > 0}
    <section>
      <h2>Waiting for your review <span class="n mono">{plural(inbox.to_review.length, 'image')}</span></h2>
      <ul>
        {#each inbox.to_review as item (item.image_id)}
          <li>
            <a
              href="/p/{item.project_id}?image={item.image_id}"
              onclick={(e) => open(e, item.project_id, item.image_id)}
            >
              <StatusDot status={item.status} />
              <span class="file mono">{item.filename}</span>
              <span class="proj">{item.project_name}</span>
            </a>
          </li>
        {/each}
      </ul>
    </section>
  {/if}
{/if}

<style>
  .head {
    margin-block-end: var(--space-6);
  }

  h1 {
    margin: 0;
    font-size: var(--text-title);
    font-weight: 500;
  }

  section {
    margin-block-end: var(--space-6);
  }

  h2 {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin: 0 0 var(--space-2);
    font-size: var(--text-heading);
    font-weight: 500;
  }

  .n {
    font-size: var(--text-small);
    font-weight: 400;
    color: var(--text-2);
  }

  ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  a {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    height: var(--h-button);
    padding-inline: var(--space-3);
    color: inherit;
    text-decoration: none;
    border-radius: var(--radius-control);
  }

  a:hover {
    background: var(--surface-1);
  }

  .file {
    font-size: var(--text-small);
  }

  .proj {
    margin-inline-start: auto;
    color: var(--text-2);
    font-size: var(--text-small);
  }

  .tag {
    padding-inline: var(--space-2);
    color: var(--warning-text);
    font-size: var(--text-overline);
    border: 1px solid var(--border);
    border-radius: var(--radius-chip);
  }

  .sk {
    height: 160px;
    background: var(--surface-1);
    border-radius: var(--radius-card);
  }
</style>
