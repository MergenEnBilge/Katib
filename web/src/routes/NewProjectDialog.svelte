<script lang="ts">
  import { api, ApiError } from '../lib/api/client';
  import type { Project } from '../lib/api/types';
  import { onboarding } from '../lib/state/onboarding.svelte';
  import Button from '../lib/ui/Button.svelte';
  import Modal from '../lib/ui/Modal.svelte';
  import TextField from '../lib/ui/TextField.svelte';

  let { oncreated, onclose }: { oncreated: (project: Project) => void; onclose: () => void } =
    $props();

  const kinds = [
    { id: 'box', label: 'Boxes', note: 'Drag a rectangle around an object.' },
    { id: 'polygon', label: 'Polygons', note: 'Click around an outline.' },
    { id: 'obb', label: 'Rotated boxes', note: 'A box that can turn, for aerial photos or text.' },
    { id: 'keypoints', label: 'Keypoints', note: 'Landmarks such as joints, in a set order.' },
    { id: 'mask', label: 'Brush masks', note: 'Paint over an area with a brush.' },
    { id: 'tag', label: 'Image tags', note: 'A label for the whole picture.' },
    { id: 'text', label: 'Text', note: 'Captions, and the words inside shapes.' },
  ];

  let name = $state('');
  let chosen = $state<string[]>(['box', 'polygon']);
  let error = $state('');
  let busy = $state(false);

  async function create(): Promise<void> {
    if (busy) return;
    error = '';
    busy = true;
    try {
      const created = await api.projects.create(name, chosen);
      onboarding.mark('project');
      oncreated(created);
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
  <fieldset class="kinds">
    <legend>What will you draw?</legend>
    {#each kinds as kind (kind.id)}
      <label>
        <input type="checkbox" value={kind.id} bind:group={chosen} />
        <span><strong>{kind.label}</strong><small>{kind.note}</small></span>
      </label>
    {/each}
    <p class="hint">You can only save the kinds you pick here.</p>
  </fieldset>
  {#snippet footer()}
    <Button onclick={onclose}>Cancel</Button>
    <Button variant="primary" disabled={busy || !name.trim() || chosen.length === 0} onclick={create}>Create project</Button>
  {/snippet}
</Modal>

<style>
  .kinds {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    margin: var(--space-3) 0 0;
    padding: 0;
    border: 0;
  }

  legend {
    padding: 0;
    margin-block-end: var(--space-1);
    font-weight: 500;
  }

  label {
    display: flex;
    gap: var(--space-2);
    align-items: flex-start;
  }

  label span {
    display: flex;
    flex-direction: column;
  }

  small,
  .hint {
    margin: 0;
    color: var(--text-2);
    font-size: var(--text-small);
  }
</style>
