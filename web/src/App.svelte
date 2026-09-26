<script lang="ts">
  import {
    CircleHelp,
    Inbox as InboxIcon,
    Layers,
    LogOut,
    Moon,
    PanelLeftClose,
    PanelLeftOpen,
    Settings as SettingsIcon,
    Sun,
  } from '@lucide/svelte';
  import { onMount } from 'svelte';
  import { i18n, t } from './lib/i18n/index.svelte';
  import { sendWaitingEdits } from './lib/sync/offline';
  import { layout } from './lib/state/layout.svelte';
  import { router } from './lib/state/router.svelte';
  import { startPractice } from './lib/state/practice';
  import { session } from './lib/state/session.svelte';
  import { applyTheme, theme } from './lib/state/theme.svelte';
  import Button from './lib/ui/Button.svelte';
  import Callout from './lib/ui/Callout.svelte';
  import EmptyState from './lib/ui/EmptyState.svelte';
  import IconButton from './lib/ui/IconButton.svelte';
  import Splash from './lib/ui/Splash.svelte';
  import Toast from './lib/ui/Toast.svelte';
  import { tourSteps, type TourName } from './lib/tour/steps';
  import Tour from './routes/workspace/Tour.svelte';
  import AuthScreen from './routes/auth/AuthScreen.svelte';
  import InviteScreen from './routes/auth/InviteScreen.svelte';
  import Inbox from './routes/Inbox.svelte';
  import Logo from './lib/ui/Logo.svelte';
  import HelpDialog from './routes/HelpDialog.svelte';
  import Projects from './routes/Projects.svelte';
  import WorkspacesDialog from './routes/WorkspacesDialog.svelte';

  $effect(applyTheme);
  i18n.init(undefined, navigator.languages);
  onMount(() => void session.load());

  // Edits made offline in an earlier visit go out as soon as someone is signed in.
  let sentWaiting = false;
  $effect(() => {
    if (session.phase === 'ready' && !sentWaiting) {
      sentWaiting = true;
      void sendWaitingEdits();
    }
  });

  let showWorkspaces = $state(false);
  let showHelp = $state(false);
  let tourName = $state<TourName | null>(null);

  function startTour(name: TourName): void {
    showHelp = false;
    if (name === 'settings') router.navigate('/settings');
    else if (name === 'home') router.navigate('/');
    tourName = name;
  }

  const route = $derived(router.route);

  function go(event: MouseEvent, to: string): void {
    event.preventDefault();
    router.navigate(to);
  }

  // "[" folds the sidebar away, the same key that folds the image list in the workspace.
  function onkeydown(event: KeyboardEvent): void {
    if (event.key !== '[' || event.ctrlKey || event.metaKey || event.altKey) return;
    const target = event.target as HTMLElement | null;
    if (target?.closest('input, textarea, select, [contenteditable="true"], dialog')) return;
    event.preventDefault();
    layout.toggle('sidebar');
  }
</script>

<svelte:window {onkeydown} />

{#if session.phase === 'loading'}
  <Splash message={t('loading')} />
{:else if session.phase === 'error'}
  <main class="center">
    <Callout tone="danger">
      {session.problem}
      {#snippet action()}<Button onclick={() => session.load()}>{t('tryAgain')}</Button>{/snippet}
    </Callout>
  </main>
{:else if session.phase === 'setup'}
  <AuthScreen kind="setup" />
{:else if route.name === 'invite'}
  {#key route.token}<InviteScreen token={route.token} />{/key}
{:else if session.phase === 'signed-out'}
  <AuthScreen kind="signin" />
{:else if route.name === 'gallery'}
  {#key route.projectId}
    {#await import('./routes/gallery/Gallery.svelte')}
      <Splash message="Opening the class gallery" />
    {:then { default: Gallery }}
      <Gallery projectId={route.projectId} />
    {/await}
  {/key}
{:else if route.name === 'workspace'}
  {#key route.projectId}
    {#await import('./routes/workspace/Workspace.svelte')}
      <Splash message="Opening your project" />
    {:then { default: Workspace }}
      <Workspace projectId={route.projectId} />
    {/await}
  {/key}
{:else}
  <div class="home" class:folded={layout.sidebar}>
    <aside class="sidebar" class:folded={layout.sidebar}>
      <div class="brand">
        <Logo size={26} wordmark={!layout.sidebar} />
        <span class="fold">
          <IconButton
            label={layout.sidebar ? t('nav.expand') : t('nav.fold')}
            shortcut="["
            onclick={() => layout.toggle('sidebar')}
          >
            {#if layout.sidebar}<PanelLeftOpen size={16} class="mirror" />{:else}<PanelLeftClose size={16} class="mirror" />{/if}
          </IconButton>
        </span>
      </div>

      <nav aria-label={t('nav.main')}>
        <a
          class="nav-item"
          href="/"
          title={t('nav.projects')}
          aria-current={route.name === 'projects' ? 'page' : undefined}
          onclick={(e) => go(e, '/')}><Layers size={16} /><span class="label">{t('nav.projects')}</span></a
        >
        <a
          class="nav-item"
          href="/inbox"
          data-tour="nav-inbox"
          title={t('nav.inbox')}
          aria-current={route.name === 'inbox' ? 'page' : undefined}
          onclick={(e) => go(e, '/inbox')}><InboxIcon size={16} /><span class="label">{t('nav.inbox')}</span></a
        >
        <a
          class="nav-item"
          href="/settings"
          data-tour="nav-settings"
          title={t('nav.settings')}
          aria-current={route.name === 'settings' ? 'page' : undefined}
          onclick={(e) => go(e, '/settings')}><SettingsIcon size={16} /><span class="label">{t('nav.settings')}</span></a
        >
        <button
          type="button"
          class="nav-item"
          data-tour="nav-help"
          title={t('nav.help')}
          onclick={() => (showHelp = true)}><CircleHelp size={16} /><span class="label">{t('nav.help')}</span></button
        >
      </nav>

      <div class="sidebar-footer">
        <button
          type="button"
          class="workspace"
          title={t('nav.workspaceHint')}
          onclick={() => (showWorkspaces = true)}
        >
          {session.mode === 'local' ? (session.user?.name ?? t('nav.signedIn')) : t('nav.localWorkspace')}
        </button>
        <span class="tools">
          {#if session.mode === 'local'}
            <IconButton label={t('nav.signOut')} onclick={() => session.signOut()}><LogOut size={16} /></IconButton>
          {/if}
          <IconButton
            label={theme.current === 'dark' ? t('theme.toLight') : t('theme.toDark')}
            onclick={() => theme.toggle()}
          >
            {#if theme.current === 'dark'}<Sun size={16} />{:else}<Moon size={16} />{/if}
          </IconButton>
        </span>
      </div>
    </aside>

    <main class="content">
      {#if route.name === 'projects'}
        <Projects />
      {:else if route.name === 'inbox'}
        <Inbox />
      {:else if route.name === 'settings'}
        {#await import('./routes/settings/Settings.svelte')}
          <Splash message="Opening settings" />
        {:then { default: Settings }}
          <Settings />
        {/await}
      {:else}
        <EmptyState
          title={t('notFound.title')}
          description={t('notFound.body')}
        >
          {#snippet icon()}<Layers size={20} />{/snippet}
          {#snippet action()}
            <Button variant="primary" onclick={() => router.navigate('/')}>{t('notFound.back')}</Button>
          {/snippet}
        </EmptyState>
      {/if}
    </main>
  </div>
  {#if showWorkspaces}<WorkspacesDialog onclose={() => (showWorkspaces = false)} />{/if}
  {#if showHelp}
    <HelpDialog
      onclose={() => (showHelp = false)}
      onsample={() => ((showHelp = false), startPractice())}
      tours={[
        { label: 'Tour of the home screen', note: 'Projects, search, settings and help.', run: () => startTour('home') },
        { label: 'Tour of Settings', note: 'What each section does and how saving works.', run: () => startTour('settings') },
      ]}
    />
  {/if}
  {#if tourName}
    <Tour
      steps={tourSteps(tourName, { types: [], hasImages: true, hasClasses: true, canManage: true, shared: session.mode === 'local' })}
      onclose={() => (tourName = null)}
    />
  {/if}
  <Toast />
{/if}

<style>
  .center {
    display: grid;
    place-items: center;
    height: 100%;
    padding: var(--space-4);
  }

  .home {
    display: grid;
    grid-template-columns: var(--sidebar-w) 1fr;
    height: 100%;
  }

  .home.folded {
    grid-template-columns: 60px 1fr;
  }

  .sidebar {
    display: flex;
    flex-direction: column;
    min-width: 0;
    background: var(--surface-1);
    border-inline-end: 1px solid var(--border);
  }

  .brand {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    height: var(--header-h);
    padding-inline: var(--space-4);
    border-block-end: 1px solid var(--border);
  }

  .folded .brand {
    justify-content: center;
    padding-inline: 0;
  }

  /* At 60px there is room for one thing, and the fold button is the one you need. */
  .folded .brand :global(.logo) {
    display: none;
  }

  nav {
    flex: 1;
    padding: var(--space-2);
  }

  .nav-item {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    height: var(--h-button);
    padding-inline: var(--space-2);
    color: var(--text-2);
    text-decoration: none;
    border-radius: var(--radius-control);
  }

  button.nav-item {
    width: 100%;
    font: inherit;
    text-align: start;
    background: none;
    border: 0;
    cursor: pointer;
  }

  .folded .nav-item {
    justify-content: center;
    padding-inline: 0;
  }

  .folded .label,
  .folded .workspace {
    display: none;
  }

  .folded .sidebar-footer {
    justify-content: center;
    padding-inline: 0;
  }

  .nav-item:hover:not([aria-current='page']) {
    background: var(--surface-2);
  }

  .nav-item[aria-current='page'] {
    color: var(--text);
    background: var(--accent-muted);
  }

  .sidebar-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-3) var(--space-4);
    border-block-start: 1px solid var(--border);
  }

  .workspace {
    padding: 0;
    text-align: start;
    background: none;
    border: 0;
    cursor: pointer;
    overflow: hidden;
    font-size: var(--text-small);
    color: var(--text-2);
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .tools {
    display: flex;
  }

  .content {
    padding: var(--page-pad);
    overflow: auto;
  }

  /* A phone shows the navigation as a bar across the top, which there is no point folding away. */
  @media (max-width: 699px) {
    .home,
    .home.folded {
      grid-template-columns: 1fr;
      grid-template-rows: auto 1fr;
    }

    .fold {
      display: none;
    }

    .folded .label {
      display: inline;
    }

    .folded .workspace {
      display: inline;
    }

    .folded .brand {
      justify-content: flex-start;
    }

    .folded .brand :global(.logo) {
      display: inline-flex;
    }

    .folded .nav-item,
    .folded .sidebar-footer {
      padding-inline: var(--space-2);
    }

    .sidebar {
      border-inline-end: 0;
      border-block-end: 1px solid var(--border);
    }

    nav {
      display: flex;
      gap: var(--space-1);
      padding-block: 0;
    }

    .brand {
      border-block-end: 0;
    }

    .content {
      padding: var(--space-4);
    }
  }
</style>
