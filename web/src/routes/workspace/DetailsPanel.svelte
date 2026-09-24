<script lang="ts">
  import { Trash } from '@lucide/svelte';
  import { boundsOf, clamp01, polygonArea } from '../../lib/canvas/geometry';
  import type { Change } from '../../lib/canvas/model';
  import { isBox, type Shape } from '../../lib/canvas/types';
  import { plural } from '../../lib/format';
  import type { Workspace } from '../../lib/state/workspace.svelte';
  import Button from '../../lib/ui/Button.svelte';

  let { ws }: { ws: Workspace } = $props();

  const shape = $derived(ws.selectedShape());
  const item = $derived(ws.current);
  const box = $derived(shape ? ws.pixelBox(shape) : null);

  function nameOf(id: string): string {
    return ws.classes.find((c) => c.id === id)?.name ?? 'Unknown';
  }

  function removeSelected(): void {
    const model = ws.engine?.model;
    if (!model) return;
    const targets = model.shapes.filter((s) => model.selection.has(s.id));
    model.commit(targets.map((s): Change => ({ kind: 'delete', shape: s })));
  }

  function setBox(field: 'x' | 'y' | 'w' | 'h', value: number): void {
    const model = ws.engine?.model;
    if (!model || !shape || !item || !isBox(shape.geometry) || Number.isNaN(value)) return;
    const g = { ...shape.geometry };
    const scale = field === 'x' || field === 'w' ? item.width : item.height;
    g[field] = value / scale;
    g.x = clamp01(g.x);
    g.y = clamp01(g.y);
    g.w = Math.min(Math.max(g.w, 0.006), 1 - g.x);
    g.h = Math.min(Math.max(g.h, 0.006), 1 - g.y);
    model.commit([
      { kind: 'update', id: shape.id, before: { geometry: shape.geometry }, after: { geometry: g } },
    ]);
  }

  const schema = $derived(ws.classes.find((c) => c.id === shape?.classId)?.attr_schema ?? []);

  function setAttr(name: string, value: unknown): void {
    const model = ws.engine?.model;
    if (!model || !shape) return;
    const attrs = { ...shape.attrs };
    if (value === '' || value === undefined) delete attrs[name];
    else attrs[name] = value;
    model.commit([
      { kind: 'update', id: shape.id, before: { attrs: shape.attrs }, after: { attrs } },
    ]);
  }

  function pixels(s: Shape): string {
    const b = boundsOf(s);
    return item ? `${Math.round(b.w * item.width)} x ${Math.round(b.h * item.height)} px` : '';
  }
</script>

<div class="panel">
  {#if ws.selectionCount === 0}
    <p class="empty">Select a shape to see its details. Click one on the image, or press Tab.</p>
  {:else if ws.selectionCount > 1}
    <p class="lead">{plural(ws.selectionCount, 'shape')} selected</p>
    <p class="hint">Press a number key to relabel them all.</p>
    <Button onclick={removeSelected}><Trash size={16} />Delete {ws.selectionCount}...</Button>
  {:else if shape}
    <div class="head">
      <span class="swatch" style:background={ws.classes.find((c) => c.id === shape.classId)?.color}></span>
      <strong>{nameOf(shape.classId)}</strong>
      <span class="type">{shape.type}</span>
    </div>

    <p class="label">Class</p>
    <div class="chips">
      {#each ws.classes as cls (cls.id)}
        <button
          type="button"
          class="cls"
          class:selected={cls.id === shape.classId}
          onclick={() => ws.chooseClass(cls.id)}
        >
          <span class="swatch small" style:background={cls.color}></span>{cls.name}
        </button>
      {/each}
    </div>

    <p class="label">Geometry</p>
    {#if box}
      <div class="grid">
        {#each ['x', 'y', 'w', 'h'] as const as field (field)}
          <label>
            <span>{field.toUpperCase()}</span>
            <input
              class="mono"
              type="number"
              min="0"
              value={box[field]}
              onchange={(e) => setBox(field, e.currentTarget.valueAsNumber)}
            />
          </label>
        {/each}
      </div>
    {:else if !isBox(shape.geometry)}
      <p class="meta mono">
        {plural(shape.geometry.points.length, 'point')}, {pixels(shape)}, area
        {item
          ? Math.round(polygonArea(shape.geometry.points) * item.width * item.height).toLocaleString()
          : 0} px
      </p>
    {/if}

    {#if schema.length > 0}
      <p class="label">Attributes</p>
      <div class="attrs">
        {#each schema as attr (attr.name)}
          {@const value = shape.attrs[attr.name]}
          <label class="attr">
            <span>{attr.name}</span>
            {#if attr.type === 'boolean'}
              <input type="checkbox" checked={value === true} onchange={(e) => setAttr(attr.name, e.currentTarget.checked)} />
            {:else if attr.type === 'enum'}
              <select onchange={(e) => setAttr(attr.name, e.currentTarget.value)}>
                <option value="" selected={value === undefined}>Not set</option>
                {#each attr.options ?? [] as option (option)}<option value={option} selected={value === option}>{option}</option>{/each}
              </select>
            {:else if attr.type === 'number'}
              <input type="number" value={typeof value === 'number' ? value : ''} onchange={(e) => setAttr(attr.name, e.currentTarget.value === '' ? '' : e.currentTarget.valueAsNumber)} />
            {:else}
              <input value={typeof value === 'string' ? value : ''} onchange={(e) => setAttr(attr.name, e.currentTarget.value)} />
            {/if}
          </label>
        {/each}
      </div>
    {/if}

    <div class="foot">
      <Button onclick={removeSelected}><Trash size={16} />Delete</Button>
    </div>
  {/if}
</div>

<style>
  .panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding: var(--space-3);
  }

  .empty,
  .hint {
    margin: 0;
    color: var(--text-2);
  }

  .lead {
    margin: 0;
    font-weight: 500;
  }

  .head {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .type {
    margin-inline-start: auto;
    font-size: var(--text-overline);
    color: var(--text-3);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .swatch {
    width: 10px;
    height: 10px;
    border-radius: var(--radius-swatch);
  }

  .swatch.small {
    flex: none;
  }

  .label {
    margin: var(--space-2) 0 0;
    font-size: var(--text-overline);
    font-weight: 500;
    color: var(--text-3);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .chips {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
  }

  .cls {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: var(--h-icon-sm);
    padding-inline: var(--space-2);
    font-size: var(--text-small);
    background: transparent;
    border: 1px solid var(--border);
    border-radius: var(--radius-chip);
    cursor: pointer;
  }

  .cls.selected {
    background: var(--accent-muted);
    border-color: var(--accent);
  }

  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-2);
  }

  label {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    color: var(--text-2);
    font-size: var(--text-small);
  }

  input {
    width: 100%;
    min-width: 0;
    height: var(--h-button-sm);
    padding-inline: var(--space-2);
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
    font-size: var(--text-small);
  }

  .meta {
    margin: 0;
    font-size: var(--text-small);
    color: var(--text-2);
  }

  .attrs {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .attr {
    display: grid;
    grid-template-columns: 90px 1fr;
    align-items: center;
  }

  .attr input:not([type='checkbox']),
  .attr select {
    height: var(--h-button-sm);
    padding-inline: var(--space-2);
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
  }

  .attr input[type='checkbox'] {
    width: 16px;
    height: 16px;
  }

  .foot {
    padding-block-start: var(--space-3);
  }
</style>
