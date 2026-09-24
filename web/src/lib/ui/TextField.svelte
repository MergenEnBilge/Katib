<script lang="ts">
  let {
    value = $bindable(''),
    label,
    placeholder = '',
    error = '',
    hint = '',
    onenter,
  }: {
    value?: string;
    label: string;
    placeholder?: string;
    error?: string;
    hint?: string;
    onenter?: () => void;
  } = $props();

  const id = `field-${Math.random().toString(36).slice(2, 8)}`;
</script>

<div class="field">
  <label for={id}>{label}</label>
  <input
    {id}
    bind:value
    {placeholder}
    aria-invalid={error ? 'true' : undefined}
    aria-describedby={error ? `${id}-error` : hint ? `${id}-hint` : undefined}
    onkeydown={(e) => e.key === 'Enter' && onenter?.()}
  />
  {#if error}
    <p class="error" id="{id}-error" role="alert">{error}</p>
  {:else if hint}
    <p class="hint" id="{id}-hint">{hint}</p>
  {/if}
</div>

<style>
  .field {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  label {
    font-weight: 500;
  }

  input {
    height: var(--h-input);
    padding-inline: 10px;
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
  }

  input[aria-invalid='true'] {
    border-color: var(--danger);
  }

  p {
    margin: 0;
    font-size: var(--text-small);
  }

  .error {
    color: var(--danger);
  }

  .hint {
    color: var(--text-2);
  }
</style>
