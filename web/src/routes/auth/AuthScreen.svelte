<script lang="ts">
  import { ApiError } from '../../lib/api/client';
  import { router } from '../../lib/state/router.svelte';
  import { session } from '../../lib/state/session.svelte';
  import Button from '../../lib/ui/Button.svelte';
  import TextField from '../../lib/ui/TextField.svelte';

  /** `setup` creates the first administrator. `signin` asks for credentials. `invite` joins a project. */
  let {
    kind,
    token = '',
    inviteText = '',
  }: { kind: 'setup' | 'signin' | 'invite'; token?: string; inviteText?: string } = $props();

  let email = $state('');
  let name = $state('');
  let password = $state('');
  let error = $state('');
  let busy = $state(false);

  const title = $derived(
    kind === 'setup' ? 'Set up Katib' : kind === 'invite' ? 'Create your account' : 'Sign in',
  );
  const lead = $derived(
    kind === 'setup'
      ? 'Create the administrator account. This screen only appears while no account exists.'
      : kind === 'invite'
        ? inviteText
        : 'Use the account you were given.',
  );

  async function submit(): Promise<void> {
    if (busy) return;
    busy = true;
    error = '';
    try {
      if (kind === 'setup') await session.setup(email, name, password);
      else if (kind === 'invite') {
        await session.accept(token, email, name, password);
        router.navigate('/');
      } else await session.signIn(email, password);
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Something went wrong. Try again.';
    } finally {
      busy = false;
    }
  }
</script>

<main class="wrap">
  <form
    class="card"
    onsubmit={(e) => {
      e.preventDefault();
      void submit();
    }}
  >
    <p class="logo">Katib</p>
    <h1>{title}</h1>
    {#if lead}<p class="lead">{lead}</p>{/if}

    <TextField label="Email" bind:value={email} placeholder="you@example.com" />
    {#if kind !== 'signin'}
      <TextField label="Your name" bind:value={name} />
    {/if}
    <label class="pw">
      <span>Password</span>
      <input
        type="password"
        bind:value={password}
        autocomplete={kind === 'signin' ? 'current-password' : 'new-password'}
        aria-invalid={error ? 'true' : undefined}
      />
      {#if kind !== 'signin'}<small>At least 10 characters.</small>{/if}
    </label>
    {#if error}<p class="error" role="alert">{error}</p>{/if}

    <Button variant="primary" disabled={busy || !email.trim() || !password} onclick={submit}
      >{kind === 'signin' ? 'Sign in' : kind === 'setup' ? 'Create administrator' : 'Create account'}</Button
    >
    <button type="submit" class="hidden" tabindex="-1" aria-hidden="true">Submit</button>
  </form>
</main>

<style>
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

  .logo {
    margin: 0;
    font-weight: 700;
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

  .pw {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    font-weight: 500;
  }

  .pw input {
    height: var(--h-input);
    padding-inline: 10px;
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
  }

  .pw input[aria-invalid='true'] {
    border-color: var(--danger);
  }

  small {
    font-weight: 400;
    color: var(--text-2);
  }

  .error {
    margin: 0;
    color: var(--danger);
    font-size: var(--text-small);
  }

  .card :global(.button) {
    justify-content: center;
  }

  .hidden {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    opacity: 0;
  }
</style>
