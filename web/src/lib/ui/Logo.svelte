<script lang="ts">
  import { brand } from '../brand';

  let { size = 28, wordmark = false }: { size?: number; wordmark?: boolean } = $props();
</script>

<span class="logo">
  <img src={brand.logo} alt={wordmark ? '' : brand.name} width={size} height={size} />
  {#if wordmark}<span class="word">{brand.name}</span>{/if}
</span>

<style>
  .logo {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
  }

  img {
    display: block;
    border-radius: 22%;
  }

  .word {
    font-weight: 700;
    font-size: var(--text-heading);
    letter-spacing: -0.01em;
  }
</style>
