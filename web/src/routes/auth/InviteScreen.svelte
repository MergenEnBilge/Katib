<script lang="ts">
  import { onMount } from 'svelte';
  import { api, ApiError } from '../../lib/api/client';
  import { appLink, isAndroidBrowser } from '../../lib/state/phone';
  import { router } from '../../lib/state/router.svelte';
  import { session } from '../../lib/state/session.svelte';
  import Button from '../../lib/ui/Button.svelte';
  import Callout from '../../lib/ui/Callout.svelte';
  import Logo from '../../lib/ui/Logo.svelte';
  import AuthScreen from './AuthScreen.svelte';

  let { token }: { token: string } = $props();

  let text = $state<string | null>(null);
  let error = $state('');
  let openInApp = $state('');
  /** Signed out: does this person need a new account, or do they already have one? */
  let haveAccount = $state(false);
  let joining = $state(false);

  async function join(): Promise<void> {
    joining = true;
    error = '';
    try {
      const { project_id } = await api.auth.join(token);
      router.navigate(`/p/${project_id}`);
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not join the project.';
    } finally {
      joining = false;
    }
  }

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

{#if error && text === null}
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
  {#if session.phase === 'ready' && session.user}
    <main class="wrap">
      <div class="card">
        <Logo size={40} wordmark />
        <h1>Join the project</h1>
        <p class="lead">{text}</p>
        {#if error}<p class="error" role="alert">{error}</p>{/if}
        <Button variant="primary" loading={joining} onclick={join}>Join as {session.user.name}</Button>
        <p class="switch">
          Not {session.user.name}?
          <button type="button" class="link" onclick={() => session.signOut()}>Sign out</button>
          to join with another account.
        </p>
      </div>
    </main>
  {:else if haveAccount}
    <AuthScreen kind="signin" inviteText={`${text} Sign in to join.`}>
      {#snippet footer()}
        New to Katib?
        <button type="button" class="link" onclick={() => (haveAccount = false)}>Make an account instead</button>
      {/snippet}
    </AuthScreen>
  {:else}
    <AuthScreen kind="invite" {token} inviteText={text}>
      {#snippet footer()}
        Already have an account?
        <button type="button" class="link" onclick={() => (haveAccount = true)}>Sign in to join</button>
      {/snippet}
    </AuthScreen>
  {/if}
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

  .card {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    width: 380px;
    max-width: 100%;
    padding: var(--space-6);
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--radius-card);
    box-shadow: var(--shadow);
  }

  .card :global(.button) {
    justify-content: center;
  }

  h1 {
    margin: 0;
    font-size: var(--text-title);
    font-weight: 500;
  }

  .lead {
    margin: 0;
    color: var(--text-2);
  }

  .error {
    margin: 0;
    color: var(--danger);
    font-size: var(--text-small);
  }

  .switch {
    margin: 0;
    font-size: var(--text-small);
    color: var(--text-2);
    text-align: center;
  }

  .link {
    padding: 0;
    color: var(--accent-text);
    text-decoration: underline;
    background: none;
    border: 0;
    cursor: pointer;
    font: inherit;
  }
</style>
