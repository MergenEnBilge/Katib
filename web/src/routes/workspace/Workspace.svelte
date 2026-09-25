<script lang="ts">
  import {
    ArrowLeft,
    Check,
    Download,
    Keyboard,
    LayoutGrid,
    Stethoscope,
    Users,
    Maximize,
    Moon,
    Brush,
    WandSparkles,
    Diamond,
    MousePointer2,
    Pentagon,
    Waypoints,
    Redo2,
    Sparkles,
    Square,
    Sun,
    Tags,
    Undo2,
    Upload,
    ZoomIn,
    ZoomOut,
    ChevronLeft,
    ChevronRight,
    PanelLeft,
    PanelRight,
  } from '@lucide/svelte';
  import { onMount } from 'svelte';
  import type { ToolName } from '../../lib/canvas/engine';
  import { resolveShortcut, type Action } from '../../lib/shortcuts/keys';
  import { router } from '../../lib/state/router.svelte';
  import { applyTheme, theme } from '../../lib/state/theme.svelte';
  import { session } from '../../lib/state/session.svelte';
  import { toasts } from '../../lib/state/toast.svelte';
  import { Workspace } from '../../lib/state/workspace.svelte';
  import Avatar from '../../lib/ui/Avatar.svelte';
  import Button from '../../lib/ui/Button.svelte';
  import Callout from '../../lib/ui/Callout.svelte';
  import EmptyState from '../../lib/ui/EmptyState.svelte';
  import IconButton from '../../lib/ui/IconButton.svelte';
  import Toast from '../../lib/ui/Toast.svelte';
  import CanvasView from './CanvasView.svelte';
  import ClassManagerDialog from './ClassManagerDialog.svelte';
  import ClassPicker from './ClassPicker.svelte';
  import ClassesPanel from './ClassesPanel.svelte';
  import DetailsPanel from './DetailsPanel.svelte';
  import ExportDialog from './ExportDialog.svelte';
  import HealthDialog from './HealthDialog.svelte';
  import HistoryDialog from './HistoryDialog.svelte';
  import ImageRail from './ImageRail.svelte';
  import ImportDialog from './ImportDialog.svelte';
  import PrelabelDialog from './PrelabelDialog.svelte';
  import ReviewPanel from './ReviewPanel.svelte';
  import ShortcutsDialog from './ShortcutsDialog.svelte';
  import TeamDialog from './TeamDialog.svelte';

  let { projectId }: { projectId: string } = $props();

  // The workspace lives as long as this component. A different project remounts it.
  // svelte-ignore state_referenced_locally
  const ws = new Workspace(projectId);

  type Dialog =
    | 'import-images'
    | 'import-labels'
    | 'export'
    | 'classes'
    | 'history'
    | 'team'
    | 'health'
    | 'shortcuts'
    | 'picker'
    | 'prelabel'
    | null;

  let tool = $state<ToolName>('select');
  let tab = $state<'classes' | 'details' | 'review'>('classes');
  let dialog = $state<Dialog>(null);
  let railCollapsed = $state(false);
  let railOpen = $state(false);
  let panelOpen = $state(false);
  let zoom = $state(100);

  const allTools: { id: ToolName; type: string | null; label: string; key: string }[] = [
    { id: 'select', type: null, label: 'Select', key: 'V' },
    { id: 'box', type: 'box', label: 'Box', key: 'B' },
    { id: 'polygon', type: 'polygon', label: 'Polygon', key: 'P' },
    { id: 'wand', type: 'polygon', label: 'Magic wand', key: 'W' },
    { id: 'obb', type: 'obb', label: 'Rotated box', key: 'O' },
    { id: 'keypoints', type: 'keypoints', label: 'Keypoints', key: 'K' },
    { id: 'brush', type: 'mask', label: 'Brush mask', key: 'R' },
  ];

  // Only show the tools this project can save shapes for.
  const tools = $derived(allTools.filter((t) => t.type === null || ws.types.includes(t.type)));

  const shared = $derived(session.mode === 'local');

  const saveLabel = $derived(
    ws.saveState === 'error'
      ? `${ws.pending} not saved`
      : ws.saveState === 'saving'
        ? ws.pending > 1
          ? `${ws.pending} pending`
          : 'Saving...'
        : 'Saved',
  );

  onMount(() => {
    void ws.init();
    const beforeUnload = (e: BeforeUnloadEvent): void => {
      if (ws.pending > 0) {
        void ws.flushNow();
        e.preventDefault();
      }
    };
    window.addEventListener('beforeunload', beforeUnload);
    return () => window.removeEventListener('beforeunload', beforeUnload);
  });

  $effect(applyTheme);

  function leave(): void {
    void ws.flushNow().finally(() => router.navigate('/'));
  }

  function showSaveStatus(): void {
    if (ws.saveState === 'saved') toasts.show('Everything is saved.');
    else if (ws.saveState === 'saving') toasts.show('Saving your latest edits.');
    else toasts.show(`${ws.pending} edits are not saved yet. Katib keeps trying.`);
  }

  function run(action: Action): void {
    const engine = ws.engine;
    if (!engine) return;
    const edits = ['undo', 'redo', 'paste', 'done'];
    if (ws.readOnly && (edits.includes(action) || action.startsWith('class:'))) return;
    if (action.startsWith('class:')) {
      const cls = ws.classByShortcut(Number(action.slice(6)));
      if (cls) ws.chooseClass(cls.id);
      return;
    }
    switch (action) {
      case 'tool:select':
      case 'tool:box':
      case 'tool:polygon':
      case 'tool:obb':
      case 'tool:keypoints':
      case 'tool:brush':
      case 'tool:wand':
        if (tools.some((t) => t.id === action.slice(5))) tool = action.slice(5) as ToolName;
        break;
      case 'class-picker':
        dialog = 'picker';
        break;
      case 'class-manager':
        dialog = 'classes';
        break;
      case 'prev':
        void ws.step(-1);
        break;
      case 'next':
        void ws.step(1);
        break;
      case 'done':
        void ws.markDone();
        break;
      case 'undo':
        engine.model.undo();
        break;
      case 'redo':
        engine.model.redo();
        break;
      case 'sync-status':
        showSaveStatus();
        break;
      case 'hide-all':
        ws.hideAll = !ws.hideAll;
        break;
      case 'zoom-in':
        engine.zoomIn();
        break;
      case 'zoom-out':
        engine.zoomOut();
        break;
      case 'zoom-fit':
        engine.fit();
        break;
      case 'toggle-rail':
        railCollapsed = !railCollapsed;
        break;
      case 'copy':
        ws.copy();
        break;
      case 'paste':
        ws.paste();
        break;
      case 'help':
        dialog = 'shortcuts';
        break;
    }
  }

  function onkeydown(e: KeyboardEvent): void {
    const target = e.target as HTMLElement;
    if (dialog || target.closest('input, textarea, select, [contenteditable="true"]')) return;
    const engine = ws.engine;
    if (!engine) return;
    if (engine.keyDown(e)) {
      e.preventDefault();
      return;
    }
    if (!e.ctrlKey && !e.metaKey && !e.altKey) {
      if (e.key === 'ArrowLeft') return void (e.preventDefault(), ws.step(-1));
      if (e.key === 'ArrowRight') return void (e.preventDefault(), ws.step(1));
    }
    const action = resolveShortcut({
      key: e.key,
      ctrl: e.ctrlKey || e.metaKey,
      shift: e.shiftKey,
      alt: e.altKey,
    });
    if (!action) return;
    e.preventDefault();
    run(action);
  }

  function onkeyup(e: KeyboardEvent): void {
    ws.engine?.keyUp(e);
  }
</script>

<svelte:window {onkeydown} {onkeyup} />

<div class="workspace">
  <header class="bar">
    <div class="group">
      <IconButton label="Back to projects" onclick={leave}><ArrowLeft size={16} /></IconButton>
      <span class="crumb" title={ws.project?.name}>{ws.project?.name ?? 'Loading'}</span>
      <span class="only-narrow">
        <IconButton label="Show images" onclick={() => ((railOpen = !railOpen), (panelOpen = false))}>
          <PanelLeft size={16} />
        </IconButton>
      </span>
    </div>

    <div class="group tools" role="group" aria-label="Tools">
      {#each tools as t (t.id)}
        <IconButton label={t.label} shortcut={t.key} onclick={() => (tool = t.id)}>
          <span class="tool" class:active={tool === t.id}>
            {#if t.id === 'select'}<MousePointer2 size={16} />{:else if t.id === 'box'}<Square size={16} />{:else if t.id === 'polygon'}<Pentagon size={16} />{:else if t.id === 'wand'}<WandSparkles size={16} />{:else if t.id === 'obb'}<Diamond size={16} />{:else if t.id === 'keypoints'}<Waypoints size={16} />{:else}<Brush size={16} />{/if}
          </span>
        </IconButton>
      {/each}
    </div>

    <div class="group">
      <span class:disabled={!ws.canUndo}>
        <IconButton label="Undo" shortcut="Ctrl+Z" onclick={() => ws.engine?.model.undo()}><Undo2 size={16} /></IconButton>
      </span>
      <span class:disabled={!ws.canRedo}>
        <IconButton label="Redo" shortcut="Ctrl+Shift+Z" onclick={() => ws.engine?.model.redo()}><Redo2 size={16} /></IconButton>
      </span>
      <span class="sep hide-narrow"></span>
      <span class="zoomtools hide-narrow">
      <IconButton label="Zoom out" shortcut="-" onclick={() => ws.engine?.zoomOut()}><ZoomOut size={16} /></IconButton>
      <span class="zoom mono">{zoom}%</span>
      <IconButton label="Zoom in" shortcut="+" onclick={() => ws.engine?.zoomIn()}><ZoomIn size={16} /></IconButton>
      <IconButton label="Fit to view" shortcut="0" onclick={() => ws.engine?.fit()}><Maximize size={16} /></IconButton>
      </span>
    </div>

    <div class="group end">
      {#if shared && ws.others.length > 0}
        <span class="presence" aria-label="Also here">
          {#each ws.others as p (p.user_id)}<Avatar name={p.name} userId={p.user_id} />{/each}
        </span>
      {/if}
      <button type="button" class="save {ws.saveState}" onclick={showSaveStatus} aria-label="Save status: {saveLabel}">
        <span class="pip"></span><span class="save-text">{saveLabel}</span>
      </button>
      <span class="hide-narrow"><Button onclick={() => (dialog = 'import-images')}><Upload size={16} />Import</Button></span>
      <span class="hide-narrow"><Button onclick={() => (dialog = 'export')}><Download size={16} />Export</Button></span>
      {#if shared}
        <span class="hide-narrow">
          <IconButton label="Team" onclick={() => (dialog = 'team')}><Users size={16} /></IconButton>
        </span>
      {/if}
      {#if ws.canManage && ws.types.includes('box')}
        <span class="hide-narrow">
          <IconButton label="Pre-label with a model" onclick={() => (dialog = 'prelabel')}><Sparkles size={16} /></IconButton>
        </span>
      {/if}
      <span class="hide-narrow">
        <IconButton label="Class gallery" onclick={() => router.navigate(`/p/${projectId}/gallery`)}><LayoutGrid size={16} /></IconButton>
      </span>
      <span class="hide-narrow">
        <IconButton label="Dataset health" onclick={() => (dialog = 'health')}><Stethoscope size={16} /></IconButton>
      </span>
      <span class="hide-narrow"><IconButton label="Class manager" shortcut="M" onclick={() => (dialog = 'classes')}><Tags size={16} /></IconButton></span>
      <span class="hide-narrow"><IconButton label="Keyboard shortcuts" shortcut="?" onclick={() => (dialog = 'shortcuts')}><Keyboard size={16} /></IconButton></span>
      <span class="hide-narrow">
        <IconButton
          label={theme.current === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
          onclick={() => theme.toggle()}
        >
          {#if theme.current === 'dark'}<Sun size={16} />{:else}<Moon size={16} />{/if}
        </IconButton>
      </span>
      <span class="only-narrow">
        <IconButton label="Show classes and details" onclick={() => ((panelOpen = !panelOpen), (railOpen = false))}>
          <PanelRight size={16} />
        </IconButton>
      </span>
    </div>
  </header>

  {#if ws.loadError && !ws.project}
    <div class="fail">
      <Callout tone="danger">
        {ws.loadError}
        {#snippet action()}
          <Button onclick={() => ws.init()}>Try again</Button>
          <Button onclick={() => router.navigate('/')}>Back to projects</Button>
        {/snippet}
      </Callout>
    </div>
  {:else}
    <div class="body">
      <div class="rail-wrap" class:open={railOpen}>
        <ImageRail
          {ws}
          collapsed={railCollapsed}
          ontoggle={() => (railCollapsed = !railCollapsed)}
          onimport={() => (dialog = 'import-images')}
        />
      </div>

      <main class="canvas">
        <CanvasView {ws} {tool} onzoom={(p) => (zoom = p)} />
        {#if ws.currentId && ws.readOnly}
          <div class="banner" role="status">
            {#if !ws.canEdit}
              <span>You have view-only access to this project.</span>
            {:else if ws.lockedByOther}
              <span>{ws.lockedByOther.name ?? 'Someone'} is editing this image. You can look around, or ask them to finish.</span>
              {#if ws.canManage}<Button onclick={() => ws.takeOver()}>Take over</Button>{/if}
            {/if}
          </div>
        {/if}
        {#if !ws.currentId && !ws.imagesLoading && ws.project}
          <div class="overlay">
            <EmptyState
              title="Nothing to annotate yet"
              description="Import images to start. You can bring labels from YOLO or COCO files afterward."
            >
              {#snippet icon()}<Upload size={20} />{/snippet}
              {#snippet action()}
                <Button variant="primary" onclick={() => (dialog = 'import-images')}>Import images</Button>
              {/snippet}
            </EmptyState>
          </div>
        {/if}
      </main>

      <aside class="panel-wrap" class:open={panelOpen} aria-label="Classes and details">
        <div class="tabs" role="tablist">
          {#each (shared ? [['classes', 'Classes'], ['details', 'Details'], ['review', 'Review']] : [['classes', 'Classes'], ['details', 'Details']]) as [id, label] (id)}
            <button type="button" role="tab" aria-selected={tab === id} class:active={tab === id} onclick={() => (tab = id as typeof tab)}>
              {label}
              {#if id === 'details' && ws.selectionCount > 0}<span class="badge mono">{ws.selectionCount}</span>{/if}
            </button>
          {/each}
        </div>

        <div class="nav">
          <IconButton label="Previous image" shortcut="A" onclick={() => ws.step(-1)}><ChevronLeft size={16} /></IconButton>
          <div class="where">
            <span class="mono pos">{ws.currentIndex >= 0 ? (ws.currentIndex + 1).toLocaleString() : 0} of {(ws.project?.image_count ?? 0).toLocaleString()}</span>
            <span class="file mono" title={ws.current?.filename}>{ws.current?.filename ?? ''}</span>
          </div>
          <IconButton label="Next image" shortcut="D" onclick={() => ws.step(1)}><ChevronRight size={16} /></IconButton>
        </div>
        <div class="done">
          {#if ws.current?.status === 'done'}
            <Button onclick={() => ws.reopen()}><Check size={16} />Done. Reopen</Button>
          {:else}
            <Button variant="primary" disabled={!ws.currentId} onclick={() => ws.markDone()}>
              <Check size={16} />Mark as done
            </Button>
          {/if}
        </div>

        <div class="tab-body">
          {#if tab === 'classes'}
            <ClassesPanel {ws} onmanage={() => (dialog = 'classes')} />
          {:else if tab === 'review'}
            <ReviewPanel {ws} />
          {:else}
            <DetailsPanel {ws} />
          {/if}
        </div>
      </aside>
    </div>
  {/if}
</div>

{#if dialog === 'import-images' || dialog === 'import-labels'}
  <ImportDialog
    projectId={ws.projectId}
    initialTab={dialog === 'import-labels' ? 'labels' : 'images'}
    ondone={() => ws.refresh()}
    onclose={() => (dialog = null)}
  />
{:else if dialog === 'export'}
  <ExportDialog {ws} onclose={() => (dialog = null)} />
{:else if dialog === 'classes'}
  <ClassManagerDialog {ws} onclose={() => (dialog = null)} onhistory={() => (dialog = 'history')} />
{:else if dialog === 'team'}
  <TeamDialog {ws} onclose={() => (dialog = null)} />
{:else if dialog === 'history'}
  <HistoryDialog {ws} onclose={() => (dialog = null)} />
{:else if dialog === 'health'}
  <HealthDialog {ws} onclose={() => (dialog = null)} />
{:else if dialog === 'shortcuts'}
  <ShortcutsDialog onclose={() => (dialog = null)} />
{:else if dialog === 'prelabel'}
  <PrelabelDialog {ws} onclose={() => (dialog = null)} />
{:else if dialog === 'picker'}
  <ClassPicker {ws} onclose={() => (dialog = null)} />
{/if}

<Toast />

<style>
  .workspace {
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  .bar {
    display: flex;
    align-items: center;
    gap: var(--space-4);
    height: 48px;
    padding-inline: var(--space-3);
    background: var(--surface-1);
    border-block-end: 1px solid var(--border);
  }

  .group {
    display: flex;
    align-items: center;
    gap: var(--space-1);
  }

  .group.end {
    margin-inline-start: auto;
    gap: var(--space-2);
  }

  .crumb {
    max-width: 200px;
    overflow: hidden;
    font-weight: 500;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .tools {
    padding: 2px;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: var(--radius-group);
  }

  .tool {
    display: grid;
    place-items: center;
    width: 30px;
    height: var(--h-icon);
    border-radius: var(--radius-control);
  }

  .tool.active {
    color: var(--accent-text);
    background: var(--accent-muted);
  }

  .presence {
    display: flex;
    margin-inline-end: var(--space-2);
  }

  .presence :global(.avatar) {
    margin-inline-start: -6px;
  }

  .banner {
    position: absolute;
    inset-block-start: var(--space-3);
    inset-inline: var(--space-3);
    z-index: 2;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding: var(--space-2) var(--space-3);
    background: var(--surface-2);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-card);
    box-shadow: var(--shadow);
  }

  .disabled {
    opacity: 0.4;
    pointer-events: none;
  }

  .sep {
    width: 1px;
    height: 20px;
    margin-inline: var(--space-1);
    background: var(--border);
  }

  .zoom {
    min-width: 44px;
    text-align: center;
    font-size: var(--text-small);
    color: var(--text-2);
  }

  .save {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    height: var(--h-icon);
    padding-inline: var(--space-2);
    font-size: var(--text-small);
    color: var(--text-2);
    background: transparent;
    border: 0;
    border-radius: var(--radius-control);
    cursor: pointer;
  }

  .save:hover {
    background: var(--surface-2);
  }

  .pip {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent);
  }

  .save.saving .pip,
  .save.error .pip {
    background: var(--warning);
  }

  .save.error {
    color: var(--warning-text);
  }

  .body {
    position: relative;
    display: flex;
    flex: 1;
    min-height: 0;
  }

  .rail-wrap {
    display: flex;
    min-height: 0;
  }

  .canvas {
    position: relative;
    flex: 1;
    min-width: 0;
    background: var(--image-bg);
  }

  .overlay {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    padding: var(--space-4);
    background: var(--bg);
  }

  .panel-wrap {
    display: flex;
    flex-direction: column;
    width: 280px;
    min-height: 0;
    background: var(--surface-1);
    border-inline-start: 1px solid var(--border);
  }

  .tabs {
    display: flex;
    height: 45px;
    border-block-end: 1px solid var(--border);
  }

  .tabs button {
    flex: 1;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    font-weight: 500;
    color: var(--text-2);
    background: transparent;
    border: 0;
    border-block-end: 2px solid transparent;
    cursor: pointer;
  }

  .tabs button.active {
    color: var(--text);
    background: var(--surface-2);
    border-block-end-color: var(--accent-text);
  }

  .badge {
    padding-inline: 5px;
    font-size: var(--text-overline);
    color: var(--text-2);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-chip);
  }

  .nav {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
  }

  .where {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: 0;
    text-align: center;
  }

  .pos {
    font-size: var(--text-small);
  }

  .file {
    overflow: hidden;
    font-size: var(--text-overline);
    color: var(--text-3);
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .done {
    padding: 0 var(--space-3) var(--space-3);
    border-block-end: 1px solid var(--border);
  }

  .done :global(.button) {
    width: 100%;
    justify-content: center;
  }

  .tab-body {
    flex: 1;
    min-height: 0;
    overflow-y: auto;
  }

  .fail {
    padding: var(--space-6);
  }

  .only-narrow {
    display: none;
  }

  @media (max-width: 1099px) {
    .only-narrow {
      display: inline-flex;
    }

    .rail-wrap,
    .panel-wrap {
      position: absolute;
      inset-block: 0;
      z-index: var(--z-menu);
      box-shadow: var(--shadow);
      transform: translateX(-110%);
      visibility: hidden;
    }

    .rail-wrap {
      inset-inline-start: 0;
    }

    .panel-wrap {
      inset-inline-end: 0;
      transform: translateX(110%);
    }

    .rail-wrap.open,
    .panel-wrap.open {
      transform: none;
      visibility: visible;
    }
  }

  @media (max-width: 699px) {
    .bar {
      gap: var(--space-1);
      padding-inline: var(--space-1);
    }

    .group.end {
      gap: 0;
    }

    .hide-narrow,
    .crumb,
    .save-text {
      display: none;
    }

    .panel-wrap {
      inset-block: auto 0;
      inset-inline: 0;
      width: 100%;
      height: 55vh;
      transform: translateY(110%);
      border-inline-start: 0;
      border-block-start: 1px solid var(--border);
    }

    .rail-wrap {
      width: 86vw;
    }

    .rail-wrap :global(.rail) {
      width: 100%;
    }
  }
</style>
