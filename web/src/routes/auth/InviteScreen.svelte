<script lang="ts">
  import { onMount } from 'svelte';
  import { api, ApiError } from '../../lib/api/client';
  import { appLink, isAndroidBrowser } from '../../lib/state/phone';
  import { router } from '../../lib/state/router.svelte';
  import Button from '../../lib/ui/Button.svelte';
  import Callout from '../../lib/ui/Callout.svelte';
  import AuthScreen from './AuthScreen.svelte';

  let { token }: { token: string } = $props();

  let text = $state<string | null>(null);
  let error = $state('');
  let openInApp = $state('');

  onMount(() => {
    api.auth
      .invite(token)
      .then((info) => {
        text = info.project
          ? `You have been invited to “${info.project}” as ${info.role}.`
          : 'You have been invited to Katib.';
        if (info.app_url && isAndroidBrowser(navigator.userAgent)) {
          openInApp = appLink(location.origin, `/invite/${token}`, info.app_url);
        }
      })
      .catch((err: unknown) => {
        error = err instanceof ApiError ? err.message : 'Could not check this invite.';
      });
  });
</script>

{#if error}
  <main class="wrap">
    <Callout tone="danger">
      {error}
      {#snippet action()}<Button onclick={() => router.navigate('/')}>Go to sign in</Button>{/snippet}
    </Callout>
  </main>
{:else if text !== null}
  {#if openInApp}
    <div class="app">
      <a class="get" href={openInApp}>Open in the Katib app</a>
      <p>You will be offered the app to install if you do not have it yet.</p>
    </div>
  {/if}
  <AuthScreen kind="invite" {token} inviteText={text} />
{/if}

<style>
  .app {
    padding: var(--space-3) var(--space-4);
    text-align: center;
    background: var(--surface-2);
    border-block-end: 1px solid var(--border);
  }

  .get {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: var(--h-button);
    padding-inline: var(--space-4);
    color: var(--on-accent);
    background: var(--accent);
    border-radius: var(--radius-control);
    font-weight: 500;
    text-decoration: none;
  }

  .app p {
    margin: var(--space-2) 0 0;
    color: var(--text-2);
    font-size: var(--text-small);
  }

  .wrap {
    display: grid;
    place-items: center;
    min-height: 100%;
    padding: var(--space-4);
  }
</style>
