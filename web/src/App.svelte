<script lang="ts">
  import { Layers, Moon, Sun } from '@lucide/svelte';
  import { applyTheme, theme } from './lib/state/theme.svelte';
  import IconButton from './lib/ui/IconButton.svelte';
  import Projects from './routes/Projects.svelte';

  $effect(applyTheme);
</script>

<div class="home">
  <aside class="sidebar">
    <div class="brand">
      <span class="logo">Katib</span>
      <span class="version mono">dev</span>
    </div>

    <nav aria-label="Main">
      <a class="nav-item" href="/" aria-current="page"><Layers size={16} />Projects</a>
    </nav>

    <div class="sidebar-footer">
      <span class="workspace">Local workspace</span>
      <IconButton
        label={theme.current === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
        onclick={() => theme.toggle()}
      >
        {#if theme.current === 'dark'}<Sun size={16} />{:else}<Moon size={16} />{/if}
      </IconButton>
    </div>
  </aside>

  <main class="content">
    <Projects />
  </main>
</div>

<style>
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
    align-items: baseline;
    gap: var(--space-2);
    height: var(--header-h);
    padding-inline: var(--space-4);
    align-items: center;
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
    font-size: var(--text-small);
    color: var(--text-2);
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
      display: none;
    }

    .content {
      padding: var(--space-4);
    }
  }
</style>
