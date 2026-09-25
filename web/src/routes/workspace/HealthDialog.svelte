<script lang="ts">
  import { api, ApiError } from '../../lib/api/client';
  import type { Health } from '../../lib/api/types';
  import { plural } from '../../lib/format';
  import { router } from '../../lib/state/router.svelte';
  import type { Workspace } from '../../lib/state/workspace.svelte';
  import Button from '../../lib/ui/Button.svelte';
  import Callout from '../../lib/ui/Callout.svelte';
  import Modal from '../../lib/ui/Modal.svelte';

  let { ws, onclose }: { ws: Workspace; onclose: () => void } = $props();

  let report = $state<Health | null>(null);
  let error = $state('');

  async function load(): Promise<void> {
    error = '';
    await ws.flushNow();
    try {
      report = await api.health(ws.projectId);
    } catch (err) {
      error = err instanceof ApiError ? err.message : 'Could not check the dataset.';
    }
  }

  $effect(() => {
    void load();
  });

  function open(imageId: string): void {
    onclose();
    void ws.open(imageId);
  }

  const total = $derived(report ? report.class_counts.reduce((a, c) => a + c.count, 0) : 0);
  const problems = $derived(
    report
      ? [report.tiny_shapes, report.duplicate_shapes, report.look_alikes.length].reduce(
          (a, b) => a + b,
          0,
        )
      : 0,
  );
</script>

<Modal
  title="Dataset health"
  description="Checks that catch common labeling mistakes before you train."
  width={620}
  {onclose}
>
  {#if error}
    <Callout tone="danger">
      {error}
      {#snippet action()}<Button onclick={load}>Try again</Button>{/snippet}
    </Callout>
  {:else if !report}
    <div class="sk" aria-busy="true"></div>
  {:else}
    <p class="summary">
      {plural(report.images, 'image')}, {plural(report.annotations, 'shape')}.
      {problems === 0 && report.empty_images === 0 ? 'Nothing needs attention.' : ''}
    </p>

    <section>
      <h3>Images without shapes <span class="n mono">{report.empty_images.toLocaleString()}</span></h3>
      <p class="d">Fine when an image really has no objects. Mark those as done.</p>
      {#if report.empty_sample.length}
        <ul>
          {#each report.empty_sample.slice(0, 8) as img (img.id)}
            <li><button type="button" class="link mono" onclick={() => open(img.id)}>{img.filename}</button></li>
          {/each}
        </ul>
        {#if report.empty_images > 8}<p class="d">and {(report.empty_images - 8).toLocaleString()} more.</p>{/if}
      {/if}
    </section>

    <section>
      <h3>Tiny shapes <span class="n mono">{report.tiny_shapes.toLocaleString()}</span></h3>
      <p class="d">Usually a stray click. Review them in the gallery and delete what is not real.</p>
      {#if report.tiny_shapes > 0}
        <Button onclick={() => router.navigate(`/p/${ws.projectId}/gallery`)}>Review in the gallery</Button>
      {/if}
    </section>

    <section>
      <h3>Duplicate shapes <span class="n mono">{report.duplicate_shapes.toLocaleString()}</span></h3>
      <p class="d">Two shapes of the same class that cover almost the same area on one image.</p>
    </section>

    <section>
      <h3>Class balance</h3>
      {#if report.imbalance !== null && report.imbalance !== undefined}
        <p class="d">
          The largest class has {report.imbalance.toFixed(1)} times as many shapes as the smallest.
          {report.imbalance >= 10 ? 'Models often struggle with gaps this large.' : ''}
        </p>
      {/if}
      <ul class="bars">
        {#each report.class_counts as c (c.name)}
          <li>
            <span class="cname">{c.name}</span>
            <span class="bar"><span style:width="{total ? (c.count / total) * 100 : 0}%"></span></span>
            <span class="mono n">{c.count.toLocaleString()}</span>
          </li>
        {/each}
      </ul>
    </section>

    <section>
      <h3>Look-alike images <span class="n mono">{report.look_alikes.length.toLocaleString()}</span></h3>
      <p class="d">Near-duplicate photos can leak between train and validation and inflate your scores.</p>
      {#each report.look_alikes.slice(0, 5) as group, i (i)}
        <p class="group">
          {#each group as img, j (img.id)}{#if j > 0}, {/if}<button type="button" class="link mono" onclick={() => open(img.id)}>{img.filename}</button>{/each}
        </p>
      {/each}
    </section>
  {/if}
  {#snippet footer()}
    <Button onclick={load}>Check again</Button>
    <Button variant="primary" onclick={onclose}>Close</Button>
  {/snippet}
</Modal>

<style>
  .summary {
    margin: 0 0 var(--space-3);
    color: var(--text-2);
  }

  section {
    padding-block: var(--space-3);
    border-block-start: 1px solid var(--border);
  }

  h3 {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin: 0 0 var(--space-1);
    font-size: var(--text-body);
    font-weight: 500;
  }

  .n {
    font-size: var(--text-small);
    font-weight: 400;
    color: var(--text-2);
  }

  .d {
    margin: 0 0 var(--space-2);
    font-size: var(--text-small);
    color: var(--text-2);
  }

  ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .link {
    padding: 0;
    color: var(--accent-text);
    background: none;
    border: 0;
    cursor: pointer;
    font-size: var(--text-small);
  }

  .group {
    margin: 0 0 var(--space-1);
    font-size: var(--text-small);
  }

  .bars li {
    display: grid;
    grid-template-columns: 110px 1fr 60px;
    align-items: center;
    gap: var(--space-2);
    height: 24px;
  }

  .cname {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .bar {
    height: 6px;
    background: var(--border);
    border-radius: 3px;
  }

  .bar span {
    display: block;
    height: 100%;
    background: var(--accent);
    border-radius: 3px;
  }

  .bars .n {
    text-align: end;
  }

  .sk {
    height: 160px;
    background: var(--surface-1);
    border-radius: var(--radius-card);
  }
</style>
