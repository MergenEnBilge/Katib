<script lang="ts">
  import { tick } from 'svelte';
  import { isDrawn } from '../../lib/canvas/types';
  import type { Workspace } from '../../lib/state/workspace.svelte';
  import { placeCard, type Rect, type TourStep } from '../../lib/tour/steps';
  import Button from '../../lib/ui/Button.svelte';

  /** `ws` is only needed by tours with a step that waits for the person to draw. */
  let { steps, ws, onclose }: { steps: TourStep[]; ws?: Workspace; onclose: () => void } = $props();

  let index = $state(0);
  let target = $state<Rect | null>(null);
  let card = $state<HTMLDivElement | undefined>();
  let place = $state({ x: 0, y: 0 });
  let drew = $state(false);

  const step = $derived(steps[index]);
  const last = $derived(index === steps.length - 1);
  const achieved = $derived(step?.until === 'shape' && drew);
  const waiting = $derived(step?.until === 'shape' && !achieved);

  /** The highlighted part's box on screen, or null when it is missing or out of view. */
  function measure(): Rect | null {
    if (!step?.target) return null;
    const el = document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    const onScreen = r.width > 0 && r.height > 0 && r.right > 0 && r.bottom > 0 && r.left < innerWidth && r.top < innerHeight;
    return onScreen ? { x: r.left, y: r.top, w: r.width, h: r.height } : null;
  }

  async function arrange(): Promise<void> {
    target = measure();
    await tick();
    const size = card ? { w: card.offsetWidth, h: card.offsetHeight } : { w: 320, h: 180 };
    place = placeCard(target, size, { w: innerWidth, h: innerHeight });
  }

  $effect(() => {
    void step;
    drew = false;
    void arrange();
    card?.querySelector<HTMLElement>('[data-next]')?.focus({ preventScroll: true });
  });

  // The practice step is done when the person draws a shape themselves, on any picture.
  $effect(() => {
    const model = ws?.engine?.model;
    if (!model || step?.until !== 'shape') return;
    return model.onChange((changes, origin) => {
      if (origin === 'edit' && changes.some((c) => c.kind === 'create' && isDrawn(c.shape))) drew = true;
    });
  });

  $effect(() => {
    const again = (): void => void arrange();
    // Screens that load on demand may not have their parts ready yet, so look again now and then.
    const timer = setInterval(again, 500);
    window.addEventListener('resize', again);
    window.addEventListener('scroll', again, true);
    return () => {
      clearInterval(timer);
      window.removeEventListener('resize', again);
      window.removeEventListener('scroll', again, true);
    };
  });

  // A finished practice step moves on by itself, after a moment to enjoy it.
  $effect(() => {
    if (!achieved) return;
    const timer = setTimeout(next, 1400);
    return () => clearTimeout(timer);
  });

  function next(): void {
    if (last) onclose();
    else index += 1;
  }

  function back(): void {
    if (index > 0) index -= 1;
  }

  function keydown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      event.stopPropagation();
      onclose();
    }
  }
</script>

<svelte:window onkeydown={keydown} />

{#if step}
  {#if target}
    <div
      class="spot"
      style:left="{target.x - 4}px"
      style:top="{target.y - 4}px"
      style:width="{target.w + 8}px"
      style:height="{target.h + 8}px"
    ></div>
  {:else}
    <div class="dim"></div>
  {/if}

  <div
    bind:this={card}
    class="card"
    role="dialog"
    aria-modal="false"
    aria-labelledby="tour-title"
    style:left="{place.x}px"
    style:top="{place.y}px"
  >
    <p class="count mono">{index + 1} of {steps.length}</p>
    <h2 id="tour-title">{step.title}</h2>
    <p class="body">{step.body}</p>
    {#if achieved}
      <p class="win" role="status">Nice. That is a label.</p>
    {/if}
    <div class="actions">
      <button type="button" class="skip" onclick={onclose}>Skip the tour</button>
      <span class="spacer"></span>
      {#if index > 0}<Button onclick={back}>Back</Button>{/if}
      <span data-next>
        <Button variant="primary" onclick={next}>
          {last ? 'Finish' : waiting ? 'Skip this step' : 'Next'}
        </Button>
      </span>
    </div>
  </div>
{/if}

<style>
  .spot {
    position: fixed;
    z-index: 70;
    pointer-events: none;
    border: 2px solid var(--accent);
    border-radius: var(--radius-group);
    box-shadow: 0 0 0 100vmax var(--scrim);
    transition:
      left 0.2s,
      top 0.2s,
      width 0.2s,
      height 0.2s;
  }

  .dim {
    position: fixed;
    inset: 0;
    z-index: 70;
    pointer-events: none;
    background: var(--scrim);
  }

  .card {
    position: fixed;
    z-index: 71;
    width: min(340px, calc(100vw - 24px));
    padding: var(--space-4);
    background: var(--surface-2);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-card);
    box-shadow: var(--shadow);
  }

  .count {
    margin: 0 0 var(--space-1);
    font-size: var(--text-overline);
    color: var(--text-3);
  }

  h2 {
    margin: 0 0 var(--space-2);
    font-size: var(--text-heading);
  }

  .body {
    margin: 0;
    color: var(--text-2);
  }

  .win {
    margin: var(--space-2) 0 0;
    font-weight: 500;
    color: var(--accent-text);
  }

  .actions {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-block-start: var(--space-4);
  }

  .spacer {
    flex: 1;
  }

  .skip {
    padding: 0;
    color: var(--text-2);
    background: none;
    border: 0;
    cursor: pointer;
    text-decoration: underline;
  }

  @media (prefers-reduced-motion: reduce) {
    .spot {
      transition: none;
    }
  }
</style>
