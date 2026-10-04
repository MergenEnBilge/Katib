<script lang="ts">
  /**
   * Making a project, in two steps: what you are labelling, then what the job is.
   *
   * Asking about the medium first is what keeps the two halves apart. A project of pictures is
   * never offered a text job, a project of text is never offered a box, and the task cards pick
   * the shapes so that most people never have to think in shapes at all.
   */
  import { FileText, Image as ImageIcon } from '@lucide/svelte';
  import { api, ApiError } from '../lib/api/client';
  import type { Project } from '../lib/api/types';
  import { onboarding } from '../lib/state/onboarding.svelte';
  import Button from '../lib/ui/Button.svelte';
  import Modal from '../lib/ui/Modal.svelte';
  import TextField from '../lib/ui/TextField.svelte';

  let { oncreated, onclose }: { oncreated: (project: Project) => void; onclose: () => void } =
    $props();

  type Medium = 'image' | 'text';

  interface Task {
    id: string;
    label: string;
    note: string;
    types: string[];
  }

  const tasks: Record<Medium, Task[]> = {
    image: [
      { id: 'detect', label: 'Find objects', note: 'A box around each thing.', types: ['box'] },
      {
        id: 'outline',
        label: 'Outline shapes',
        note: 'Trace an edge, or paint over an area.',
        types: ['polygon', 'mask'],
      },
      {
        id: 'obb',
        label: 'Angled boxes',
        note: 'Boxes that turn, for aerial photos or signs.',
        types: ['obb'],
      },
      {
        id: 'pose',
        label: 'Pose and landmarks',
        note: 'Points in a set order, joined up.',
        types: ['keypoints'],
      },
      {
        id: 'sort-photos',
        label: 'Sort photographs',
        note: 'One or more labels for the whole picture.',
        types: ['tag'],
      },
      {
        id: 'caption',
        label: 'Caption or read',
        note: 'Write what a picture shows, or the words in it.',
        types: ['text', 'box'],
      },
    ],
    text: [
      {
        id: 'entities',
        label: 'Find things in the words',
        note: 'Label names, places, amounts: anything written in the text.',
        types: ['span'],
      },
      {
        id: 'relations',
        label: 'Find things and how they relate',
        note: 'Label things in the words, then join them: who works where, what caused what.',
        types: ['span', 'relation'],
      },
      {
        id: 'sort-documents',
        label: 'Sort documents',
        note: 'One or more labels for a whole document.',
        types: ['tag'],
      },
      {
        id: 'write',
        label: 'Write an answer',
        note: 'A summary, a translation, or a reply to each document.',
        types: ['text'],
      },
      {
        id: 'everything',
        label: 'All of these',
        note: 'Label things in the words, join them up, sort documents and write answers.',
        types: ['span', 'relation', 'tag', 'text'],
      },
    ],
  };

  /** The individual shapes, for the people who would rather pick them themselves. */
  const kinds: Record<Medium, { id: string; label: string; note: string }[]> = {
    image: [
      { id: 'box', label: 'Boxes', note: 'Drag a rectangle around an object.' },
      { id: 'polygon', label: 'Polygons', note: 'Click around an outline.' },
      {
        id: 'obb',
        label: 'Rotated boxes',
        note: 'A box that can turn, for aerial photos or text.',
      },
      { id: 'keypoints', label: 'Keypoints', note: 'Landmarks such as joints, in a set order.' },
      { id: 'mask', label: 'Brush masks', note: 'Paint over an area with a brush.' },
      { id: 'tag', label: 'Image tags', note: 'A label for the whole picture.' },
      { id: 'text', label: 'Text', note: 'Captions, and the words inside shapes.' },
    ],
    text: [
      { id: 'span', label: 'Spans', note: 'Label a run of words inside a document.' },
      {
        id: 'relation',
        label: 'Relations',
        note: 'A link from one span to another, such as who works where.',
      },
      { id: 'tag', label: 'Document labels', note: 'A label for a whole document.' },
      { id: 'text', label: 'Written answers', note: 'Words you write about a document.' },
    ],
  };

  let name = $state('');
  let medium = $state<Medium>('image');
  let task = $state('detect');
  let custom = $state<string[]>(['box', 'polygon']);
  let error = $state('');
  let busy = $state(false);

  const picked = $derived(tasks[medium].find((t) => t.id === task) ?? null);
  const chosen = $derived(task === 'custom' ? custom : (picked?.types ?? []));

  /** Starting again on the other medium: its tasks and shapes are not the same ones. */
  function chooseMedium(next: Medium): void {
    if (medium === next) return;
    medium = next;
    task = tasks[next][0]?.id ?? 'custom';
    custom = next === 'text' ? ['span'] : ['box', 'polygon'];
  }

  async function create(): Promise<void> {
    if (busy || chosen.length === 0) return;
    error = '';
    busy = true;
    try {
      const created = await api.projects.create(name, chosen, medium);
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
  description="A project holds what you are labelling, its classes and every label on it."
  {onclose}
>
  <TextField
    label="Project name"
    placeholder={medium === 'text' ? 'Customer reviews' : 'Street scenes'}
    bind:value={name}
    {error}
    onenter={create}
  />

  <fieldset>
    <legend>What are you labelling?</legend>
    <div class="mediums" role="radiogroup" aria-label="What are you labelling">
      <button
        type="button"
        class="medium"
        class:on={medium === 'image'}
        role="radio"
        aria-checked={medium === 'image'}
        onclick={() => chooseMedium('image')}
      >
        <ImageIcon size={22} />
        <strong>Pictures</strong>
        <small>Photographs, scans, frames from a video.</small>
      </button>
      <button
        type="button"
        class="medium"
        class:on={medium === 'text'}
        role="radio"
        aria-checked={medium === 'text'}
        onclick={() => chooseMedium('text')}
      >
        <FileText size={22} />
        <strong>Text</strong>
        <small>Documents, reviews, messages, transcripts.</small>
      </button>
    </div>
  </fieldset>

  <fieldset>
    <legend>What is the job?</legend>
    <div class="tasks" role="radiogroup" aria-label="What is the job">
      {#each tasks[medium] as option (option.id)}
        <button
          type="button"
          class="task"
          class:on={task === option.id}
          role="radio"
          aria-checked={task === option.id}
          onclick={() => (task = option.id)}
        >
          <strong>{option.label}</strong>
          <small>{option.note}</small>
        </button>
      {/each}
      <button
        type="button"
        class="task"
        class:on={task === 'custom'}
        role="radio"
        aria-checked={task === 'custom'}
        onclick={() => (task = 'custom')}
      >
        <strong>Choose the shapes myself</strong>
        <small>Pick exactly what this project can save.</small>
      </button>
    </div>
  </fieldset>

  {#if task === 'custom'}
    <fieldset class="kinds">
      <legend>Shapes this project can save</legend>
      {#each kinds[medium] as kind (kind.id)}
        <label>
          <input type="checkbox" value={kind.id} bind:group={custom} />
          <span><strong>{kind.label}</strong><small>{kind.note}</small></span>
        </label>
      {/each}
    </fieldset>
  {/if}

  <p class="hint">You can only save the kinds this project uses, so the toolbar stays short.</p>

  {#snippet footer()}
    <Button onclick={onclose}>Cancel</Button>
    <Button
      variant="primary"
      loading={busy}
      disabled={!name.trim() || chosen.length === 0}
      onclick={create}>Create project</Button
    >
  {/snippet}
</Modal>

<style>
  fieldset {
    margin: var(--space-3) 0 0;
    padding: 0;
    border: 0;
  }

  legend {
    padding: 0;
    margin-block-end: var(--space-2);
    font-weight: 500;
  }

  .mediums,
  .tasks {
    display: grid;
    gap: var(--space-2);
  }

  .mediums {
    grid-template-columns: 1fr 1fr;
  }

  .tasks {
    grid-template-columns: 1fr 1fr;
  }

  .medium,
  .task {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: var(--space-3);
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: var(--radius-control);
    color: var(--text);
    font: inherit;
    text-align: start;
    cursor: pointer;
  }

  .medium {
    align-items: center;
    text-align: center;
    gap: var(--space-1);
  }

  .medium:hover,
  .task:hover {
    border-color: var(--border-strong);
  }

  .medium.on,
  .task.on {
    background: var(--accent-muted);
    border-color: var(--accent);
  }

  .kinds {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
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

  .hint {
    margin-block-start: var(--space-3);
  }

  @media (max-width: 599px) {
    .tasks {
      grid-template-columns: 1fr;
    }
  }
</style>
