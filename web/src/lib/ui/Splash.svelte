<script lang="ts">
  import { brand } from '../brand';
  import Spinner from './Spinner.svelte';

  let { message = 'Loading' }: { message?: string } = $props();
</script>

<div class="splash" role="status" aria-live="polite">
  <img src={brand.logo} alt="" width="72" height="72" />
  <p class="name">{brand.name}</p>
  <p class="message"><Spinner size={16} />{message}</p>
</div>

<style>
  .splash {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    height: 100%;
    min-height: 240px;
    color: var(--text);
  }

  img {
    border-radius: 22%;
    animation: rise 0.5s ease-out both;
  }

  .name {
    margin: 0;
    font-size: var(--text-title);
    font-weight: 700;
  }

  .message {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin: 0;
    color: var(--text-2);
  }

  @keyframes rise {
    from {
      opacity: 0;
      transform: translateY(6px) scale(0.96);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    img {
      animation: none;
    }
  }
</style>
