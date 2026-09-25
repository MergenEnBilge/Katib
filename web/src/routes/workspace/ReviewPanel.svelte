<script lang="ts">
  import { Check, RotateCcw } from '@lucide/svelte';
  import { relativeTime } from '../../lib/format';
  import type { Workspace } from '../../lib/state/workspace.svelte';
  import Button from '../../lib/ui/Button.svelte';

  let { ws }: { ws: Workspace } = $props();

  let text = $state('');
  let busy = $state(false);

  const item = $derived(ws.current);
  const reviewOn = $derived(ws.project?.review_enabled ?? false);
  const reviewable = $derived(
    reviewOn && ws.canReview && !!item && ['done', 'approved', 'rejected'].includes(item.status),
  );
  const open = $derived(ws.comments.filter((c) => !c.resolved));
  const resolved = $derived(ws.comments.filter((c) => c.resolved));

  async function send(): Promise<void> {
    if (!text.trim() || busy) return;
    busy = true;
    await ws.addComment(text);
    text = '';
    busy = false;
  }
</script>

<div class="panel">
  {#if !item}
    <p class="note">Open an image to see its comments.</p>
  {:else}
    {#if ws.canManage && ws.members.length > 0}
      <label class="assign">
        <span>Assigned to</span>
        <select
          value={item.assignee_id ?? ''}
          onchange={(e) => ws.assignCurrent(e.currentTarget.value || null)}
        >
          <option value="">Nobody</option>
          {#each ws.members as m (m.user.id)}<option value={m.user.id}>{m.user.name}</option>{/each}
        </select>
      </label>
    {/if}
    {#if reviewOn}
      <p class="state">
        Status: <strong>{item.status === 'in_progress' ? 'in progress' : item.status}</strong>
      </p>
      {#if reviewable}
        <div class="actions">
          <Button
            variant="primary"
            disabled={item.status === 'approved'}
            onclick={() => ws.review('approved')}><Check size={16} />Approve</Button
          >
          <Button disabled={item.status === 'rejected'} onclick={() => ws.review('rejected')}
            ><RotateCcw size={16} />Send back</Button
          >
        </div>
      {:else if ws.canReview && item.status !== 'done'}
        <p class="note">Review starts once the image is marked as done.</p>
      {/if}
    {:else}
      <p class="note">Review is off for this project. Turn it on under Team, Settings.</p>
    {/if}

    <p class="label">Comments</p>
    {#if ws.comments.length === 0}
      <p class="note">No comments on this image.</p>
    {/if}
    <ul>
      {#each open as c (c.id)}
        <li>
          <p class="meta"><strong>{c.author}</strong> <span>{relativeTime(c.created_at)}</span></p>
          <p class="body">{c.body}</p>
          <button type="button" class="link" onclick={() => ws.resolveComment(c.id, true)}>Resolve</button>
        </li>
      {/each}
      {#each resolved as c (c.id)}
        <li class="done">
          <p class="meta"><strong>{c.author}</strong> <span>resolved</span></p>
          <p class="body">{c.body}</p>
          <button type="button" class="link" onclick={() => ws.resolveComment(c.id, false)}>Reopen</button>
        </li>
      {/each}
    </ul>

    {#if ws.canEdit}
      <form
        onsubmit={(e) => {
          e.preventDefault();
          void send();
        }}
      >
        <textarea
          rows="3"
          placeholder="Add a comment"
          aria-label="Add a comment"
          bind:value={text}
        ></textarea>
        <Button disabled={busy || !text.trim()} onclick={send}>Comment</Button>
      </form>
    {/if}
  {/if}
</div>

<style>
  .panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding: var(--space-3);
  }

  .note,
  .state {
    margin: 0;
    color: var(--text-2);
    font-size: var(--text-small);
  }

  .assign {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    color: var(--text-2);
    font-size: var(--text-small);
  }

  .assign select {
    height: var(--h-button-sm);
    padding-inline: var(--space-2);
    color: var(--text);
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
  }

  .actions {
    display: flex;
    gap: var(--space-2);
  }

  .label {
    margin: var(--space-2) 0 0;
    font-size: var(--text-overline);
    font-weight: 500;
    color: var(--text-3);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    padding-block: var(--space-2);
    border-block-end: 1px solid var(--border);
  }

  li.done .body {
    color: var(--text-3);
  }

  .meta {
    display: flex;
    gap: var(--space-2);
    margin: 0;
    font-size: var(--text-small);
  }

  .meta span {
    color: var(--text-3);
  }

  .body {
    margin: var(--space-1) 0;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  .link {
    padding: 0;
    color: var(--accent-text);
    background: none;
    border: 0;
    font-size: var(--text-small);
    cursor: pointer;
  }

  form {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    align-items: flex-start;
  }

  textarea {
    width: 100%;
    padding: var(--space-2);
    resize: vertical;
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
    font: inherit;
  }
</style>
