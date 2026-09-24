<script lang="ts">
  import { colorFor, initials } from '../sync/realtime';

  let { name, userId, size = 20 }: { name: string; userId: string; size?: number } = $props();
</script>

<span
  class="avatar"
  title={name}
  role="img"
  aria-label={name}
  style:background={colorFor(userId)}
  style:width="{size}px"
  style:height="{size}px"
  style:font-size="{Math.round(size * 0.45)}px">{initials(name)}</span
>

<style>
  .avatar {
    display: inline-grid;
    place-items: center;
    flex: none;
    color: #0b0e0c;
    font-weight: 500;
    border-radius: 50%;
    border: 2px solid var(--surface-1);
  }
</style>
