<script lang="ts">
  import { Check, Sparkles } from '@lucide/svelte';
  import { onboarding } from '../lib/state/onboarding.svelte';
  import Button from '../lib/ui/Button.svelte';

  let {
    onsample,
    onnew,
    busy = false,
  }: { onsample: () => void; onnew: () => void; busy?: boolean } = $props();
</script>

<section class="card" aria-labelledby="start-title">
  <div class="intro">
    <h2 id="start-title">Welcome to Katib</h2>
    <p>
      Katib helps you draw labels on pictures so you can train a model. Not sure where to begin? Try
      the practice project. It comes with pictures, classes and a guided tour, and takes about two minutes.
    </p>
    <div class="buttons">
      <Button variant="primary" disabled={busy} onclick={onsample}>
        <Sparkles size={16} />{busy ? 'Making it...' : 'Try it with practice pictures'}
      </Button>
      <Button onclick={onnew}>Start my own project</Button>
    </div>
  </div>

  <div class="steps">
    <p class="progress mono">{onboarding.count} of {onboarding.steps.length} done</p>
    <ol>
      {#each onboarding.steps as step (step.id)}
        <li class:done={onboarding.isDone(step.id)}>
          <span class="tick" aria-hidden="true">{#if onboarding.isDone(step.id)}<Check size={12} strokeWidth={3} />{/if}</span>
          <span class="text">
            <strong>{step.title}</strong><small>{step.hint}</small>
            <span class="sr-only">{onboarding.isDone(step.id) ? ' (done)' : ''}</span>
          </span>
        </li>
      {/each}
    </ol>
    <button type="button" class="hide" onclick={() => onboarding.dismiss()}>Hide this. I know my way around</button>
  </div>
</section>

<style>
  .card {
    display: grid;
    grid-template-columns: 1.1fr 1fr;
    gap: var(--space-8);
    margin-block-end: var(--space-6);
    padding: var(--space-6);
    background: linear-gradient(135deg, var(--accent-muted), var(--surface-1) 60%);
    border: 1px solid var(--border);
    border-radius: var(--radius-card);
  }

  h2 {
    margin: 0 0 var(--space-2);
    font-size: var(--text-title);
  }

  .intro p {
    margin: 0;
    max-width: 52ch;
    color: var(--text-2);
  }

  .buttons {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-block-start: var(--space-4);
  }

  .progress {
    margin: 0 0 var(--space-2);
    font-size: var(--text-small);
    color: var(--text-2);
  }

  ol {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: flex;
    gap: var(--space-3);
    align-items: flex-start;
  }

  .tick {
    display: inline-grid;
    place-items: center;
    flex: none;
    width: 18px;
    height: 18px;
    margin-block-start: 1px;
    color: var(--on-accent);
    border: 1.5px solid var(--text-3);
    border-radius: 50%;
  }

  li.done .tick {
    background: var(--accent);
    border-color: var(--accent);
  }

  li.done strong {
    color: var(--text-2);
    text-decoration: line-through;
  }

  .text {
    display: flex;
    flex-direction: column;
  }

  small {
    color: var(--text-2);
    font-size: var(--text-small);
  }

  .hide {
    margin-block-start: var(--space-3);
    padding: 0;
    font-size: var(--text-small);
    color: var(--text-2);
    text-decoration: underline;
    background: none;
    border: 0;
    cursor: pointer;
  }

  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
  }

  @media (max-width: 899px) {
    .card {
      grid-template-columns: 1fr;
      gap: var(--space-4);
      padding: var(--space-4);
    }
  }
</style>
