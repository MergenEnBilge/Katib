<script lang="ts">
  import { Inbox as InboxIcon, Layers, LogOut, Moon, Sun } from '@lucide/svelte';
  import { onMount } from 'svelte';
  import { router } from './lib/state/router.svelte';
  import { session } from './lib/state/session.svelte';
  import { applyTheme, theme } from './lib/state/theme.svelte';
  import Button from './lib/ui/Button.svelte';
  import Callout from './lib/ui/Callout.svelte';
  import EmptyState from './lib/ui/EmptyState.svelte';
  import IconButton from './lib/ui/IconButton.svelte';
  import Toast from './lib/ui/Toast.svelte';
  import AuthScreen from './routes/auth/AuthScreen.svelte';
  import InviteScreen from './routes/auth/InviteScreen.svelte';
  import Gallery from './routes/gallery/Gallery.svelte';
  import Inbox from './routes/Inbox.svelte';
  import Projects from './routes/Projects.svelte';
  import WorkspacesDialog from './routes/WorkspacesDialog.svelte';
  import Workspace from './routes/workspace/Workspace.svelte';

  $effect(applyTheme);
  onMount(() => void session.load());

  let showWorkspaces = $state(false);

  const route = $derived(router.route);

  function go(event: MouseEvent, to: string): void {
    event.preventDefault();
    router.navigate(to);
  }
</script>

{#if session.phase === 'loading'}
  <div class="splash" role="status" aria-label="Loading"></div>
{:else if session.phase === 'error'}
  <main class="center">
    <Callout tone="danger">
      {session.problem}
      {#snippet action()}<Button onclick={() => session.load()}>Try again</Button>{/snippet}
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
    <Gallery projectId={route.projectId} />
  {/key}
{:else if route.name === 'workspace'}
  {#key route.projectId}
    <Workspace projectId={route.projectId} />
  {/key}
{:else}
  <div class="home">
    <aside class="sidebar">
      <div class="brand">
        <span class="logo">Katib</span>
        <span class="version mono">dev</span>
      </div>

      <nav aria-label="Main">
        <a
          class="nav-item"
          href="/"
          aria-current={route.name === 'projects' ? 'page' : undefined}
          onclick={(e) => go(e, '/')}><Layers size={16} />Projects</a
        >
        <a
          class="nav-item"
          href="/inbox"
          aria-current={route.name === 'inbox' ? 'page' : undefined}
          onclick={(e) => go(e, '/inbox')}><InboxIcon size={16} />Inbox</a
        >
      </nav>

      <div class="sidebar-footer">
        <button
          type="button"
          class="workspace"
          title="Share this computer or switch to another server"
          onclick={() => (showWorkspaces = true)}
        >
          {session.mode === 'local' ? (session.user?.name ?? 'Signed in') : 'Local workspace'}
        </button>
        <span class="tools">
          {#if session.mode === 'local'}
            <IconButton label="Sign out" onclick={() => session.signOut()}><LogOut size={16} /></IconButton>
          {/if}
          <IconButton
            label={theme.current === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
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
      {:else}
        <EmptyState
          title="Page not found"
          description="This address does not match anything in Katib."
        >
          {#snippet icon()}<Layers size={20} />{/snippet}
          {#snippet action()}
            <Button variant="primary" onclick={() => router.navigate('/')}>Back to projects</Button>
          {/snippet}
        </EmptyState>
      {/if}
    </main>
  </div>
  {#if showWorkspaces}<WorkspacesDialog onclose={() => (showWorkspaces = false)} />{/if}
  <Toast />
{/if}

<style>
  .splash,
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

  .sidebar {
    display: flex;
    flex-direction: column;
    background: var(--surface-1);
    border-inline-end: 1px solid var(--border);
  }

  .brand {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    height: var(--header-h);
    padding-inline: var(--space-4);
    border-block-end: 1px solid var(--border);
  }

  .logo {
    font-weight: 700;
    font-size: var(--text-heading);
  }

  .version {
    font-size: var(--text-overline);
    color: var(--text-3);
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

  @media (max-width: 699px) {
    .home {
      grid-template-columns: 1fr;
      grid-template-rows: auto 1fr;
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
