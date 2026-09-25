<script lang="ts">
  import { toasts } from '../state/toast.svelte';
</script>

<div class="region" aria-live="polite">
  {#if toasts.current}
    {@const toast = toasts.current}
    <!-- svelte-ignore a11y_no_static_element_interactions -->
    <div
      class="toast"
      onpointerenter={() => toasts.hold()}
      onpointerleave={() => toasts.release()}
      onfocusin={() => toasts.hold()}
      onfocusout={() => toasts.release()}
    >
      <span>{toast.message}</span>
      {#if toast.action}
        {@const action = toast.action}
        <button
          type="button"
          onclick={() => {
            action.run();
            toasts.dismiss();
          }}>{action.label}</button
        >
      {/if}
    </div>
  {/if}
</div>

<style>
  .region {
    position: fixed;
    inset-inline: 0;
    inset-block-end: 20px;
    z-index: var(--z-toast);
    display: flex;
    justify-content: center;
    pointer-events: none;
  }

  .toast {
    pointer-events: auto;
    display: flex;
    align-items: center;
    gap: var(--space-4);
    max-width: 640px;
    padding: var(--space-3) var(--space-4);
    background: var(--surface-2);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-card);
    box-shadow: var(--shadow);
  }

  button {
    background: none;
    border: 0;
    padding: 0;
    color: var(--accent-text);
    font-weight: 500;
    cursor: pointer;
  }
</style>
