<script lang="ts">
  import { Plus, Trash, X } from '@lucide/svelte';
  import { untrack } from 'svelte';
  import { api, ApiError } from '../../lib/api/client';
  import type { AttrDef, ClassOp } from '../../lib/api/types';
  import { plural } from '../../lib/format';
  import { DEFAULT_PALETTE } from '../../lib/palette';
  import type { Workspace } from '../../lib/state/workspace.svelte';
  import Button from '../../lib/ui/Button.svelte';
  import Callout from '../../lib/ui/Callout.svelte';
  import Modal from '../../lib/ui/Modal.svelte';

  let { ws, onclose, onhistory }: { ws: Workspace; onclose: () => void; onhistory: () => void } =
    $props();

  type Mode = 'edit' | 'merge' | 'delete';

  // svelte-ignore state_referenced_locally
  let selectedId = $state<string | null>(ws.activeClassId ?? ws.classes[0]?.id ?? null);
  let query = $state('');
  let error = $state('');
  let draft = $state('');
  let mode = $state<Mode>('edit');
  let targetId = $state<string | null>(null);
  let preview = $state<ClassOp | null>(null);
  let previewing = $state(false);
  let confirmName = $state('');
  let busy = $state(false);
  let attrs = $state<AttrDef[]>([]);
  let attrError = $state('');

  const filtered = $derived(
    ws.classes.filter((c) => c.name.toLowerCase().includes(query.trim().toLowerCase())),
  );
  const selected = $derived(ws.classes.find((c) => c.id === selectedId) ?? null);
  const targets = $derived(ws.classes.filter((c) => c.id !== selectedId));
  const target = $derived(ws.classes.find((c) => c.id === targetId) ?? null);

  // Reset the editor only when a different class is chosen, not when counts refresh.
  $effect(() => {
    void selectedId;
    untrack(() => {
      draft = selected?.name ?? '';
      attrs = structuredClone($state.snapshot(selected?.attr_schema ?? [])) as AttrDef[];
      error = '';
      attrError = '';
      mode = 'edit';
      preview = null;
      confirmName = '';
      targetId = null;
    });
  });

  // Fetch a preview whenever the choice changes. Nothing is changed by a dry run.
  $effect(() => {
    const id = selectedId;
    const to = targetId;
    const m = mode;
    if (!id || (m === 'merge' && !to) || m === 'edit') return;
    let stale = false;
    previewing = true;
    (m === 'merge' && to ? api.classes.merge(id, to, true) : api.classes.remove(id, true))
      .then((p) => {
        if (!stale) preview = p;
      })
      .catch((err: unknown) => {
        if (!stale) error = err instanceof ApiError ? err.message : 'Could not preview that.';
      })
      .finally(() => {
        if (!stale) previewing = false;
      });
    return () => {
      stale = true;
    };
  });

  async function rename(): Promise<void> {
    if (!selected || draft.trim() === selected.name) return;
    try {
      await ws.renameClass(selected.id, draft);
      error = '';
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not rename the class.';
    }
  }

  async function recolor(color: string): Promise<void> {
    if (!selected) return;
    try {
      await ws.recolorClass(selected.id, color);
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not change the color.';
    }
  }

  async function saveAttrs(): Promise<void> {
    if (!selected) return;
    attrError = '';
    const clean = attrs.map((a) => ({
      name: a.name,
      type: a.type,
      ...(a.type === 'enum'
        ? { options: (a.options ?? []).map((o) => o.trim()).filter(Boolean) }
        : {}),
    })) as AttrDef[];
    try {
      await api.classes.update(selected.id, { attr_schema: clean });
      await ws.refreshClasses();
    } catch (err) {
      attrError = err instanceof ApiError ? err.message : 'Could not save the attributes.';
    }
  }

  async function confirm(): Promise<void> {
    if (!selected || busy) return;
    busy = true;
    error = '';
    const from = selected;
    try {
      const done =
        mode === 'merge' && targetId
          ? await api.classes.merge(from.id, targetId, false)
          : await api.classes.remove(from.id, false);
      ws.announce(done.operation?.summary ?? 'Done.', done.operation?.id);
      await ws.reloadCurrent();
      selectedId = mode === 'merge' ? targetId : (ws.classes[0]?.id ?? null);
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'That did not work.';
    } finally {
      busy = false;
    }
  }

  function summaryLine(p: ClassOp): string {
    const a = plural(p.preview.annotations, 'annotation');
    const i = plural(p.preview.images, 'image');
    if (mode === 'merge' && selected && target) {
      const drop =
        p.preview.dropped_attr_values > 0
          ? ` ${plural(p.preview.dropped_attr_values, 'attribute value')} that “${target.name}” does not define will be dropped.`
          : '';
      return `${a} on ${i} will be relabeled from “${selected.name}” to “${target.name}”. “${selected.name}” is removed afterward.${drop}`;
    }
    return `This will remove ${a} from ${i}.`;
  }
</script>

<Modal
  title="Class manager"
  description="Rename, recolor, merge or delete a class. Annotations follow a rename automatically because they point at the class, not its name."
  width={760}
  {onclose}
>
  <div class="layout">
    <div class="left">
      <input type="search" placeholder="Search classes" aria-label="Search classes" bind:value={query} />
      <ul>
        {#each filtered as cls (cls.id)}
          <li>
            <button
              type="button"
              class="row"
              class:selected={cls.id === selectedId}
              onclick={() => (selectedId = cls.id)}
            >
              <span class="swatch" style:background={cls.color}></span>
              <span class="name">{cls.name}</span>
              <span class="count mono">{cls.annotation_count.toLocaleString()}</span>
            </button>
          </li>
        {:else}
          <li class="none">No class matches.</li>
        {/each}
      </ul>
    </div>

    <div class="right">
      {#if !selected}
        <p class="note">Choose a class on the left.</p>
      {:else if mode === 'edit'}
        <label class="field">
          <span>Name</span>
          <input
            bind:value={draft}
            aria-invalid={error ? 'true' : undefined}
            onblur={rename}
            onkeydown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
          />
        </label>
        {#if error}<p class="error" role="alert">{error}</p>{/if}
        <p class="note">The old name stays as an alias, so label files that still use it import into this class.</p>

        <p class="label">Color</p>
        <div class="swatches">
          {#each DEFAULT_PALETTE as color (color)}
            <button
              type="button"
              class="pick"
              class:on={selected.color.toLowerCase() === color.toLowerCase()}
              style:background={color}
              aria-label="Use {color}"
              aria-pressed={selected.color.toLowerCase() === color.toLowerCase()}
              onclick={() => recolor(color)}
            ></button>
          {/each}
          <input
            class="picker"
            type="color"
            aria-label="Pick another color"
            value={selected.color}
            onchange={(e) => recolor(e.currentTarget.value)}
          />
        </div>

        <p class="label">Attributes</p>
        {#each attrs as attr, i (i)}
          <div class="attr">
            <input aria-label="Attribute name" placeholder="Name" bind:value={attr.name} />
            <select aria-label="Attribute type" bind:value={attr.type}>
              <option value="boolean">Yes or no</option>
              <option value="enum">One of</option>
              <option value="text">Text</option>
              <option value="number">Number</option>
            </select>
            <button type="button" class="x" aria-label="Remove attribute" onclick={() => (attrs = attrs.filter((_, n) => n !== i))}><X size={14} /></button>
            {#if attr.type === 'enum'}
              <input
                class="wide"
                aria-label="Options, separated by commas"
                placeholder="small, medium, large"
                value={(attr.options ?? []).join(', ')}
                oninput={(e) => (attr.options = e.currentTarget.value.split(','))}
              />
            {/if}
          </div>
        {/each}
        <div class="attr-actions">
          <Button onclick={() => (attrs = [...attrs, { name: '', type: 'boolean' }])}><Plus size={16} />Add attribute</Button>
          <Button onclick={saveAttrs}>Save attributes</Button>
        </div>
        {#if attrError}<p class="error" role="alert">{attrError}</p>{/if}
        <p class="note">Removing an attribute keeps the values already stored. They reappear if you add it back.</p>

        <p class="label">Usage</p>
        <p class="meta mono">{plural(selected.annotation_count, 'annotation')}</p>

        <div class="actions">
          <Button disabled={targets.length === 0} onclick={() => (mode = 'merge')}>Merge into...</Button>
          <Button variant="danger-quiet" onclick={() => (mode = 'delete')}>Delete...</Button>
        </div>
      {:else if mode === 'merge'}
        <p class="lead">Merge “{selected.name}” into</p>
        <div class="targets" role="radiogroup" aria-label="Merge into">
          {#each targets as cls (cls.id)}
            <label class="radio" class:on={targetId === cls.id}>
              <input type="radio" name="target" value={cls.id} bind:group={targetId} />
              <span class="swatch" style:background={cls.color}></span>
              <span class="name">{cls.name}</span>
              <span class="count mono">{cls.annotation_count.toLocaleString()}</span>
            </label>
          {/each}
        </div>
        {#if previewing}<p class="note">Counting...</p>{:else if preview}<Callout>{summaryLine(preview)}</Callout>{/if}
        {#if error}<p class="error" role="alert">{error}</p>{/if}
        <div class="actions">
          <Button onclick={() => (mode = 'edit')}>Cancel</Button>
          <Button variant="primary" disabled={!preview || busy || !targetId} onclick={confirm}>
            {preview ? `Merge ${plural(preview.preview.annotations, 'annotation')}` : 'Merge'}
          </Button>
        </div>
      {:else}
        <p class="lead">Delete “{selected.name}”?</p>
        <Callout tone="danger">
          {#if previewing}Counting...{:else if preview}{summaryLine(preview)}{/if}
          Deleting a class removes every annotation that uses it.
        </Callout>
        <label class="field">
          <span>Type {selected.name} to confirm</span>
          <input bind:value={confirmName} aria-label="Type the class name to confirm" />
        </label>
        {#if error}<p class="error" role="alert">{error}</p>{/if}
        <div class="actions">
          <Button onclick={() => (mode = 'edit')}>Cancel</Button>
          <Button
            variant="danger"
            disabled={busy || confirmName !== selected.name}
            onclick={confirm}
          ><Trash size={16} />Delete class</Button>
        </div>
      {/if}
    </div>
  </div>
  {#snippet footer()}
    <Button onclick={onhistory}>History...</Button>
    <Button variant="primary" onclick={onclose}>Done</Button>
  {/snippet}
</Modal>

<style>
  .layout {
    display: grid;
    grid-template-columns: 240px 1fr;
    gap: var(--space-4);
    min-height: 360px;
  }

  .left {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    min-height: 0;
  }

  input,
  select {
    height: var(--h-button-sm);
    padding-inline: var(--space-2);
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
  }

  input[aria-invalid='true'] {
    border-color: var(--danger);
  }

  ul {
    margin: 0;
    padding: 0;
    overflow-y: auto;
    list-style: none;
  }

  .row,
  .radio {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    height: var(--h-button);
    padding: 0 var(--space-2);
    text-align: start;
    background: transparent;
    border: 0;
    border-radius: var(--radius-control);
    cursor: pointer;
  }

  .row:hover,
  .radio:hover {
    background: var(--surface-1);
  }

  .row.selected,
  .radio.on {
    background: var(--accent-muted);
  }

  .radio input {
    height: auto;
  }

  .swatch {
    width: 10px;
    height: 10px;
    border-radius: var(--radius-swatch);
  }

  .name {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .count {
    font-size: var(--text-overline);
    color: var(--text-2);
  }

  .none {
    padding: var(--space-2);
    color: var(--text-2);
  }

  .right {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    min-width: 0;
  }

  .lead {
    margin: 0;
    font-size: var(--text-heading);
    font-weight: 500;
  }

  .targets {
    max-height: 200px;
    overflow-y: auto;
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    font-weight: 500;
  }

  .field input {
    height: var(--h-input);
    font-weight: 400;
  }

  .error {
    margin: 0;
    font-size: var(--text-small);
    color: var(--danger);
  }

  .note,
  .meta {
    margin: 0;
    font-size: var(--text-small);
    color: var(--text-2);
  }

  .label {
    margin: var(--space-2) 0 0;
    font-size: var(--text-overline);
    font-weight: 500;
    color: var(--text-3);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .swatches {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
  }

  .pick {
    width: 24px;
    height: 24px;
    border: 2px solid transparent;
    border-radius: var(--radius-chip);
    cursor: pointer;
  }

  .pick.on {
    border-color: var(--text);
  }

  .picker {
    width: 32px;
    padding: 2px;
  }

  .attr {
    display: grid;
    grid-template-columns: 1fr 110px 28px;
    gap: var(--space-1);
  }

  .attr .wide {
    grid-column: 1 / -1;
  }

  .x {
    display: grid;
    place-items: center;
    color: var(--text-2);
    background: transparent;
    border: 0;
    cursor: pointer;
  }

  .attr-actions,
  .actions {
    display: flex;
    gap: var(--space-2);
    margin-block-start: var(--space-2);
  }

  .actions {
    justify-content: flex-end;
    margin-block-start: auto;
  }

  @media (max-width: 699px) {
    .layout {
      grid-template-columns: 1fr;
    }
  }
</style>
