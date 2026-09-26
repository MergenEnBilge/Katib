<script lang="ts">
  import { onMount } from 'svelte';
  import { api } from '../../lib/api/client';
  import { Engine, type ToolName } from '../../lib/canvas/engine';
  import Spinner from '../../lib/ui/Spinner.svelte';
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
      segment: async (clicks) => {
        const imageId = ws.currentId;
        if (!imageId) return null;
        const found = await api.ml.segment(ws.projectId, imageId, clicks);
        return found.points.map(([x, y]) => [x, y] as [number, number]);
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

<!-- What the current tool wants you to do next. The zoom reading lives in the toolbar. -->
{#if hint}
  <div class="chip" aria-live="off">{hint}</div>
{/if}
{#if ws.imageLoading}
  <div class="loading" role="status"><Spinner size={16} />Loading image</div>
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
    max-width: calc(100% - 2 * var(--space-3));
    padding: 4px var(--space-3);
    overflow: hidden;
    color: var(--text-2);
    font-size: var(--text-small);
    text-overflow: ellipsis;
    white-space: nowrap;
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--radius-control);
    pointer-events: none;
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
