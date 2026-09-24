<script lang="ts">
  import { onMount } from 'svelte';
  import { api, ApiError } from '../../lib/api/client';
  import { router } from '../../lib/state/router.svelte';
  import Button from '../../lib/ui/Button.svelte';
  import Callout from '../../lib/ui/Callout.svelte';
  import AuthScreen from './AuthScreen.svelte';

  let { token }: { token: string } = $props();

  let text = $state<string | null>(null);
  let error = $state('');

  onMount(() => {
    api.auth
      .invite(token)
      .then((info) => {
        text = info.project
          ? `You have been invited to “${info.project}” as ${info.role}.`
          : 'You have been invited to Katib.';
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
  <AuthScreen kind="invite" {token} inviteText={text} />
{/if}

<style>
  .wrap {
    display: grid;
    place-items: center;
    min-height: 100%;
    padding: var(--space-4);
  }
</style>
