<script lang="ts">
  import { Layers, Plus, Search } from '@lucide/svelte';
  import { api, ApiError } from '../lib/api/client';
  import type { Project } from '../lib/api/types';
  import { relativeTime } from '../lib/format';
  import { t, tp } from '../lib/i18n/index.svelte';
  import { onboarding } from '../lib/state/onboarding.svelte';
  import { router } from '../lib/state/router.svelte';
  import { startPractice } from '../lib/state/practice';
  import Button from '../lib/ui/Button.svelte';
  import Callout from '../lib/ui/Callout.svelte';
  import EmptyState from '../lib/ui/EmptyState.svelte';
  import GetStarted from './GetStarted.svelte';
  import NewProjectDialog from './NewProjectDialog.svelte';

  let projects = $state<Project[] | null>(null);
  let error = $state('');
  let search = $state('');
  let creating = $state(false);
  let loaded = false;

  async function load(): Promise<void> {
    error = '';
    try {
      projects = await api.projects.list(search.trim() || undefined);
      loaded = true;
    } catch (err) {
      error = err instanceof ApiError ? err.message : t('projects.loadFailed');
    }
  }

  $effect(() => {
    void search;
    const timer = setTimeout(load, loaded ? 200 : 0);
    return () => clearTimeout(timer);
  });

  $effect(() => {
    function keydown(event: KeyboardEvent): void {
      const target = event.target as HTMLElement;
      if (target.closest('input, textarea, [role="dialog"]') || event.ctrlKey || event.metaKey) return;
      if (event.key.toLowerCase() === 'n') {
        event.preventDefault();
        creating = true;
      }
    }
    window.addEventListener('keydown', keydown);
    return () => window.removeEventListener('keydown', keydown);
  });

  let makingSample = $state(false);

  async function practice(): Promise<void> {
    makingSample = true;
    await startPractice();
    makingSample = false;
  }

  function open(event: MouseEvent, project: Project): void {
    if (event.metaKey || event.ctrlKey || event.shiftKey) return;
    event.preventDefault();
    router.navigate(`/p/${project.id}`);
  }
</script>

<header class="page-header">
  <h1>{t('projects.title')}</h1>
  <div class="actions">
    <label class="search">
      <Search size={16} aria-hidden="true" />
      <input type="search" placeholder={t('projects.search')} aria-label={t('projects.search')} bind:value={search} />
    </label>
    <Button variant="primary" onclick={() => (creating = true)}>
      <Plus size={16} />{t('projects.new')}
    </Button>
  </div>
</header>

{#if onboarding.visible && projects !== null && !error}
  <GetStarted onsample={practice} onnew={() => (creating = true)} busy={makingSample} />
{/if}

{#if error}
  <Callout tone="danger">
    {error}
    {#snippet action()}<Button onclick={load}>{t('tryAgain')}</Button>{/snippet}
  </Callout>
{:else if projects === null}
  <div class="grid" aria-busy="true">
    {#each [1, 2, 3] as n (n)}<div class="skeleton"></div>{/each}
  </div>
{:else if projects.length === 0 && !search.trim() && onboarding.visible}
  <!-- The welcome card above already says what to do. -->
{:else if projects.length === 0 && !search.trim()}
  <EmptyState
    title={t('projects.empty.title')}
    description={t('projects.empty.body')}
  >
    {#snippet icon()}<Layers size={20} />{/snippet}
    {#snippet action()}
      <Button variant="primary" onclick={() => (creating = true)}><Plus size={16} />{t('projects.new')}</Button>
    {/snippet}
  </EmptyState>
{:else if projects.length === 0}
  <p class="none">{t('projects.noMatch', { query: search.trim() })}</p>
{:else}
  <div class="grid">
    {#each projects as project (project.id)}
      <a class="card" href="/p/{project.id}" onclick={(e) => open(e, project)}>
        <div class="cover"></div>
        <div class="info">
          <h2 title={project.name}>{project.name}</h2>
          <p class="meta">{tp('projects.images', project.image_count)}</p>
          <div
            class="bar"
            role="progressbar"
            aria-label={t('projects.doneLabel')}
            aria-valuemin="0"
            aria-valuemax={project.image_count}
            aria-valuenow={project.done_count}
          >
            <span
              style:width="{project.image_count
                ? (project.done_count / project.image_count) * 100
                : 0}%"
            ></span>
          </div>
          <p class="foot">
            <span class="mono">{t('projects.done', { done: project.done_count.toLocaleString(), total: project.image_count.toLocaleString() })}</span>
            <span>{t('projects.edited', { when: relativeTime(project.last_edited ?? project.created_at) })}</span>
          </p>
        </div>
      </a>
    {/each}
  </div>
{/if}

{#if creating}
  <NewProjectDialog
    onclose={() => (creating = false)}
    oncreated={(project) => {
      creating = false;
      router.navigate(`/p/${project.id}`);
    }}
  />
{/if}

<style>
  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
    margin-block-end: var(--space-6);
  }

  h1 {
    margin: 0;
    font-size: var(--text-title);
    font-weight: 500;
  }

  .actions {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  .search {
    position: relative;
    display: flex;
    align-items: center;
    color: var(--text-3);
  }

  .search :global(svg) {
    position: absolute;
    inset-inline-start: 10px;
    pointer-events: none;
  }

  .search input {
    width: 220px;
    height: var(--h-button);
    padding-inline: 32px 10px;
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
    gap: var(--space-4);
  }

  .card {
    display: flex;
    flex-direction: column;
    overflow: hidden;
    color: inherit;
    text-decoration: none;
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: var(--radius-card);
    transition: border-color var(--dur-hover) ease-out;
  }

  .card:hover {
    border-color: var(--border-strong);
  }

  .cover {
    height: 128px;
    background: repeating-linear-gradient(135deg, var(--stripe) 0 8px, transparent 8px 16px),
      var(--image-bg);
  }

  .info {
    padding: var(--space-3) var(--space-4) var(--space-4);
  }

  h2 {
    margin: 0;
    overflow: hidden;
    font-size: var(--text-heading);
    font-weight: 500;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .meta {
    margin: var(--space-1) 0 var(--space-3);
    color: var(--text-2);
    font-size: var(--text-small);
  }

  .bar {
    height: 4px;
    overflow: hidden;
    background: var(--border);
    border-radius: 2px;
  }

  .bar span {
    display: block;
    height: 100%;
    background: var(--accent);
  }

  .foot {
    display: flex;
    justify-content: space-between;
    margin: var(--space-2) 0 0;
    color: var(--text-3);
    font-size: var(--text-small);
  }

  .skeleton {
    height: 250px;
    background: var(--surface-2);
    border-radius: var(--radius-card);
  }

  .none {
    color: var(--text-2);
  }

  @media (max-width: 699px) {
    .page-header {
      flex-direction: column;
      align-items: stretch;
    }

    .search input {
      width: 100%;
    }

    .search {
      flex: 1;
    }
  }
</style>
