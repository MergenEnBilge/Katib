<script lang="ts">
  import { Lock } from '@lucide/svelte';
  import type { Snippet } from 'svelte';
  import type { SettingField } from '../../lib/api/types';

  let {
    field,
    value,
    onchange,
    extra,
  }: {
    field: SettingField;
    value: unknown;
    onchange: (value: unknown) => void;
    extra?: Snippet;
  } = $props();

  const id = $derived(`setting-${field.key.replace(/\./g, '-')}`);
  const locked = $derived(field.source === 'environment');
  const known = $derived(field.options.some((o) => o.value === value));
  // A choice that also takes typed text shows a text box once "Other" is picked.
  let other = $state(false);
  const showOther = $derived(field.allow_other && (other || (!known && value !== '')));

  const lines = $derived(Array.isArray(value) ? (value as string[]).join('\n') : '');

  function pick(next: string): void {
    if (next === '__other') {
      other = true;
      return;
    }
    other = false;
    onchange(next);
  }
</script>

<div class="row">
  <div class="label">
    <label for={id}>{field.label}</label>
    <span class="chips">
      {#if locked}
        <span class="chip locked" title="Set by {field.env_name}"><Lock size={11} />Set by the environment</span>
      {:else if field.restart_pending}
        <span class="chip warn">Needs a restart</span>
      {:else if !field.live}
        <span class="chip">Applies after a restart</span>
      {/if}
    </span>
  </div>

  <div class="control">
    {#if field.kind === 'bool'}
      <label class="switch">
        <input {id} type="checkbox" role="switch" checked={value === true} disabled={locked} onchange={(e) => onchange(e.currentTarget.checked)} />
        <span>{value === true ? 'On' : 'Off'}</span>
      </label>
    {:else if field.kind === 'int'}
      <input
        {id}
        type="number"
        class="mono"
        min={field.minimum ?? undefined}
        max={field.maximum ?? undefined}
        value={typeof value === 'number' ? value : ''}
        disabled={locked}
        onchange={(e) => onchange(e.currentTarget.valueAsNumber)}
      />
    {:else if field.kind === 'choice'}
      <select {id} value={showOther ? '__other' : String(value)} disabled={locked} onchange={(e) => pick(e.currentTarget.value)}>
        {#each field.options as option (option.value)}<option value={option.value}>{option.label}</option>{/each}
        {#if field.allow_other}<option value="__other">Another address</option>{/if}
      </select>
      {#if showOther}
        <input aria-label="{field.label}, custom" class="mono" value={String(value)} disabled={locked} onchange={(e) => onchange(e.currentTarget.value)} />
      {/if}
    {:else if field.kind === 'paths'}
      <textarea
        {id}
        rows="3"
        class="mono"
        spellcheck="false"
        placeholder="One folder per line"
        value={lines}
        disabled={locked}
        onchange={(e) => onchange(e.currentTarget.value.split('\n').map((l) => l.trim()).filter(Boolean))}
      ></textarea>
    {:else}
      <input {id} class="mono" spellcheck="false" autocomplete="off" value={String(value ?? '')} disabled={locked} onchange={(e) => onchange(e.currentTarget.value)} />
    {/if}
    {#if extra}{@render extra()}{/if}
  </div>

  <p class="help">{field.help}{#if locked} To change it, edit <span class="mono">{field.env_name}</span> where Katib is started.{/if}</p>
</div>

<style>
  .row {
    display: grid;
    grid-template-columns: minmax(180px, 1fr) minmax(220px, 1.4fr);
    gap: var(--space-1) var(--space-6);
    padding-block: var(--space-4);
    border-block-end: 1px solid var(--border);
  }

  .label {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    align-items: flex-start;
  }

  label {
    font-weight: 500;
  }

  .chips {
    display: flex;
    gap: var(--space-1);
  }

  .chip {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    height: var(--h-chip);
    padding-inline: var(--space-2);
    font-size: var(--text-small);
    color: var(--text-2);
    background: var(--surface-2);
    border: 1px solid var(--border);
    border-radius: var(--radius-chip);
  }

  .chip.warn {
    color: var(--warning-text);
    border-color: var(--warning);
  }

  .control {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  input:not([type='checkbox']),
  select,
  textarea {
    padding-inline: 10px;
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
  }

  input:not([type='checkbox']),
  select {
    height: var(--h-input);
  }

  textarea {
    padding-block: var(--space-2);
    resize: vertical;
  }

  input:disabled,
  select:disabled,
  textarea:disabled {
    color: var(--text-3);
    background: var(--surface-1);
  }

  .switch {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    font-weight: 400;
    color: var(--text-2);
  }

  .help {
    grid-column: 1 / -1;
    margin: 0;
    max-width: 68ch;
    font-size: var(--text-small);
    color: var(--text-2);
  }

  @media (max-width: 699px) {
    .row {
      grid-template-columns: 1fr;
    }
  }
</style>
