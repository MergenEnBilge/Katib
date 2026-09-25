<script lang="ts">
  /** A spinning ring. It follows the text color, so it suits any button or background. */
  let { size = 18, label = '' }: { size?: number; label?: string } = $props();
</script>

<span class="spinner" style:width="{size}px" style:height="{size}px" role={label ? 'status' : undefined} aria-label={label || undefined} aria-hidden={label ? undefined : 'true'}></span>

<style>
  .spinner {
    display: inline-block;
    flex: none;
    box-sizing: border-box;
    border: 2px solid color-mix(in srgb, currentColor 22%, transparent);
    border-top-color: currentColor;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }

  /* Motion is optional. A slow pulse still shows that something is happening. */
  @media (prefers-reduced-motion: reduce) {
    .spinner {
      animation: pulse 1.6s ease-in-out infinite;
      border-top-color: color-mix(in srgb, currentColor 22%, transparent);
      background: color-mix(in srgb, currentColor 30%, transparent);
    }

    @keyframes pulse {
      50% {
        opacity: 0.35;
      }
    }
  }
</style>
