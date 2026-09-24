<script lang="ts">
  import { api, ApiError } from '../lib/api/client';
  import type { Project } from '../lib/api/types';
  import Button from '../lib/ui/Button.svelte';
  import Modal from '../lib/ui/Modal.svelte';
  import TextField from '../lib/ui/TextField.svelte';

  let { oncreated, onclose }: { oncreated: (project: Project) => void; onclose: () => void } =
    $props();

  let name = $state('');
  let error = $state('');
  let busy = $state(false);

  async function create(): Promise<void> {
    if (busy) return;
    error = '';
    busy = true;
    try {
      oncreated(await api.projects.create(name));
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not create the project.';
    } finally {
      busy = false;
    }
  }
</script>

<Modal
  title="New project"
  description="A project holds a set of images, its classes and every annotation."
  {onclose}
>
  <TextField
    label="Project name"
    placeholder="Street scenes"
    bind:value={name}
    {error}
    onenter={create}
  />
  {#snippet footer()}
    <Button onclick={onclose}>Cancel</Button>
    <Button variant="primary" disabled={busy || !name.trim()} onclick={create}>Create project</Button>
  {/snippet}
</Modal>
