<script lang="ts">
  import { onMount } from 'svelte';
  import { Engine, type ToolName } from '../../lib/canvas/engine';
  import { toasts } from '../../lib/state/toast.svelte';
  import type { Workspace } from '../../lib/state/workspace.svelte';

  let {
    ws,
    tool,
    crosshair = false,
    onzoom,
  }: {
    ws: Workspace;
    tool: ToolName;
    crosshair?: boolean;
    onzoom?: (percent: number) => void;
  } = $props();

  let host: HTMLDivElement;
  let hint = $state('');
  let zoom = $state(100);

  onMount(() => {
    // The engine reports its first view change from inside its constructor, before this
    // variable is assigned, so the callback has to tolerate that.
    let engine: Engine | undefined;
    engine = new Engine(host, {
      activeClassId: () => ws.activeClassId,
      needClass: () => toasts.show('Add a class in the Classes tab, then draw.'),
      onHint: (text) => (hint = text),
      onView: () => {
        if (!engine) return;
        zoom = engine.viewport.percent;
        onzoom?.(zoom);
      },
    });
    zoom = engine.viewport.percent;
    ws.attach(engine);
    return () => {
      ws.detach();
      engine?.dispose();
    };
  });

  $effect(() => {
    ws.engine?.setTool(tool);
  });

  $effect(() => {
    const engine = ws.engine;
    if (!engine) return;
    engine.hideAll = ws.hideAll;
    engine.opacity = ws.opacity;
    engine.patternMode = ws.patternMode;
    engine.readOnly = ws.readOnly;
    engine.crosshair = crosshair;
    engine.setClasses(ws.styles);
  });
</script>

<div class="stage" bind:this={host} role="application" aria-label="Annotation canvas"></div>

<div class="chip" aria-live="off">
  <span class="mono">{zoom}%</span>
  <span class="hint">{hint}</span>
</div>
{#if ws.imageLoading}
  <div class="loading" role="status">Loading image</div>
{/if}

<style>
  .stage {
    position: absolute;
    inset: 0;
    overflow: hidden;
    background: var(--image-bg);
  }

  .chip {
    position: absolute;
    inset-block-end: var(--space-3);
    inset-inline-start: var(--space-3);
    display: flex;
    gap: var(--space-3);
    max-width: calc(100% - 2 * var(--space-3));
    padding: 4px var(--space-3);
    color: var(--text-2);
    font-size: var(--text-small);
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--radius-control);
    pointer-events: none;
  }

  .hint {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .loading {
    position: absolute;
    inset-block-start: var(--space-3);
    inset-inline-start: 50%;
    transform: translateX(-50%);
    padding: 4px var(--space-3);
    color: var(--text-2);
    font-size: var(--text-small);
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--radius-control);
  }
</style>
