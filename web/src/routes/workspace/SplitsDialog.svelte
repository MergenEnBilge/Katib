<script lang="ts">
  import { Dices } from '@lucide/svelte';
  import { api, ApiError } from '../../lib/api/client';
  import type { SplitState } from '../../lib/api/types';
  import { plural } from '../../lib/format';
  import { KIND_LABELS, SPLIT_LABELS, SPLIT_NAMES, toPercent } from '../../lib/splits';
  import type { Workspace } from '../../lib/state/workspace.svelte';
  import Button from '../../lib/ui/Button.svelte';
  import Callout from '../../lib/ui/Callout.svelte';
  import Modal from '../../lib/ui/Modal.svelte';

  let { ws, onclose }: { ws: Workspace; onclose: () => void } = $props();

  let info = $state<SplitState | null>(null);
  let error = $state('');
  let kind = $state('detect');
  let weights = $state({ train: 80, val: 10, test: 10 });
  let seed = $state(0);
  let stratify = $state(false);
  let onlyNew = $state(false);
  let preview = $state<{ counts: Record<string, number>; moved: number } | null>(null);
  let confirming = $state(false);
  let busy = $state(false);

  const total = $derived((info?.counts.train ?? 0) + (info?.counts.val ?? 0) + (info?.counts.test ?? 0) + (info?.counts.none ?? 0));
  const percent = $derived(toPercent(weights));
  const canEdit = $derived(ws.canManage);
  const hasSplit = $derived(total > 0 && (info?.counts.none ?? 0) < total);

  $effect(() => {
    api.splits
      .get(ws.projectId)
      .then((s) => {
        info = s;
        kind = s.kind;
        weights = {
          train: Math.round((s.ratios.train ?? 0) * 100),
          val: Math.round((s.ratios.val ?? 0) * 100),
          test: Math.round((s.ratios.test ?? 0) * 100),
        };
        seed = s.seed;
        stratify = s.stratify;
      })
      .catch((err) => (error = err instanceof ApiError ? err.message : 'Could not load the split.'));
  });

  function useKind(next: string): void {
    kind = next;
    const preset = info?.presets[next];
    if (!preset) return;
    weights = {
      train: Math.round((preset.train ?? 0) * 100),
      val: Math.round((preset.val ?? 0) * 100),
      test: Math.round((preset.test ?? 0) * 100),
    };
  }

  function body(dryRun: boolean) {
    return {
      ratios: { train: weights.train, val: weights.val, test: weights.test },
      seed,
      stratify,
      only_unassigned: onlyNew,
      dry_run: dryRun,
    };
  }

  // Ask the server what would happen whenever a choice changes, so nothing is a surprise.
  $effect(() => {
    void [weights.train, weights.val, weights.test, seed, stratify, onlyNew];
    confirming = false;
    if (!info || weights.train + weights.val + weights.test <= 0) {
      preview = null;
      return;
    }
    const timer = setTimeout(() => {
      api.splits
        .shuffle(ws.projectId, body(true))
        .then((r) => {
          preview = { counts: r.counts, moved: r.moved };
          error = '';
        })
        .catch((err) => {
          preview = null;
          error = err instanceof ApiError ? err.message : 'Could not preview the split.';
        });
    }, 200);
    return () => clearTimeout(timer);
  });

  async function apply(): Promise<void> {
    if (hasSplit && !confirming && !onlyNew) {
      confirming = true;
      return;
    }
    busy = true;
    error = '';
    try {
      const done = await api.splits.shuffle(ws.projectId, body(false));
      info = await api.splits.get(ws.projectId);
      confirming = false;
      ws.announce(`Split ${plural(done.moved, 'image')} changed.`, done.operation?.id);
      await ws.loadImages(true);
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not split the images.';
    } finally {
      busy = false;
    }
  }

  function width(count: number): string {
    return total ? `${(count / total) * 100}%` : '0%';
  }
</script>

<Modal
  title="Train, validation and test"
  description="Choose which images are for training, for checking progress and for the final test. Katib saves the split on your images, so exports and imports agree."
  width={560}
  {onclose}
>
  {#if info}
    <div class="bar" role="img" aria-label="Images in each split">
      {#each [...SPLIT_NAMES, 'none' as const] as name (name)}
        <span class="seg {name}" style:width={width(info.counts[name] ?? 0)}></span>
      {/each}
    </div>
    <ul class="legend">
      {#each [...SPLIT_NAMES, 'none' as const] as name (name)}
        <li><span class="swatch {name}"></span>{SPLIT_LABELS[name]} <b class="mono">{(info.counts[name] ?? 0).toLocaleString()}</b></li>
      {/each}
    </ul>

    {#if total === 0}
      <Callout>Import some images first, then come back to divide them up.</Callout>
    {:else if canEdit}
      <div class="form">
        <label class="field">
          <span>Kind of dataset</span>
          <select value={kind} onchange={(e) => useKind(e.currentTarget.value)}>
            {#each Object.keys(info.presets) as k (k)}<option value={k}>{KIND_LABELS[k] ?? k}</option>{/each}
          </select>
          <small>Picks a sensible starting ratio. Change the numbers below to make it your own.</small>
        </label>

        <div class="ratios">
          {#each SPLIT_NAMES as name (name)}
            <label>
              <span>{SPLIT_LABELS[name]} <em class="mono">{percent[name]}%</em></span>
              <input type="number" min="0" max="100" bind:value={weights[name]} aria-label="{SPLIT_LABELS[name]} share" />
            </label>
          {/each}
        </div>

        <div class="seed">
          <label>
            <span>Shuffle seed</span>
            <input type="number" bind:value={seed} />
          </label>
          <Button onclick={() => (seed = Math.floor(Math.random() * 100000))}><Dices size={16} />New shuffle</Button>
        </div>

        <label class="check"><input type="checkbox" bind:checked={stratify} /> Keep rare classes in every split</label>
        <label class="check"><input type="checkbox" bind:checked={onlyNew} /> Only place images that have no split yet</label>
      </div>

      {#if preview}
        <p class="preview" aria-live="polite">
          {SPLIT_NAMES.map((n) => `${(preview?.counts[n] ?? 0).toLocaleString()} ${SPLIT_LABELS[n].toLowerCase()}`).join(', ')}.
          {#if preview.moved === 0}Nothing would change.{:else}{plural(preview.moved, 'image')} would change split.{/if}
        </p>
      {/if}
      {#if confirming}
        <Callout>This changes the split of {plural(preview?.moved ?? 0, 'image')}. You can undo it from History for 30 days.</Callout>
      {/if}
    {:else}
      <Callout>Only managers can change the split.</Callout>
    {/if}
  {/if}
  {#if error}<Callout tone="danger">{error}</Callout>{/if}

  {#snippet footer()}
    <Button onclick={onclose}>Close</Button>
    {#if canEdit && total > 0}
      <Button variant="primary" loading={busy} disabled={!preview || preview.moved === 0} onclick={apply}>
        {confirming ? 'Yes, shuffle' : hasSplit && !onlyNew ? 'Reshuffle' : 'Split images'}
      </Button>
    {/if}
  {/snippet}
</Modal>

<style>
  .bar {
    display: flex;
    height: 14px;
    overflow: hidden;
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--radius-chip);
  }

  .seg.train,
  .swatch.train {
    background: var(--accent);
  }

  .seg.val,
  .swatch.val {
    background: var(--warning);
  }

  .seg.test,
  .swatch.test {
    background: var(--text-2);
  }

  .seg.none,
  .swatch.none {
    background: var(--border-strong);
  }

  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-4);
    margin: var(--space-2) 0 var(--space-4);
    padding: 0;
    list-style: none;
    font-size: var(--text-small);
    color: var(--text-2);
  }

  .legend li {
    display: flex;
    align-items: center;
    gap: var(--space-1);
  }

  .swatch {
    width: 10px;
    height: 10px;
    border-radius: var(--radius-swatch);
  }

  .form {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    font-weight: 500;
  }

  small {
    font-weight: 400;
    color: var(--text-2);
  }

  select,
  input[type='number'] {
    height: var(--h-input);
    padding-inline: var(--space-2);
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
  }

  .ratios {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--space-3);
  }

  .ratios label,
  .seed label {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    font-weight: 500;
  }

  em {
    font-style: normal;
    font-weight: 400;
    color: var(--text-2);
  }

  .seed {
    display: flex;
    align-items: flex-end;
    gap: var(--space-3);
  }

  .check {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .preview {
    margin: var(--space-3) 0;
    color: var(--text-2);
  }
</style>
