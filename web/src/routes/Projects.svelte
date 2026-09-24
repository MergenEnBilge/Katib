<script lang="ts">
  import { Layers, Plus } from '@lucide/svelte';
  import Button from '../lib/ui/Button.svelte';
  import EmptyState from '../lib/ui/EmptyState.svelte';
</script>

<header class="page-header">
  <h1>Projects</h1>
</header>

<EmptyState
  title="No projects yet"
  description="A project holds a set of images, its classes and every annotation."
>
  {#snippet icon()}<Layers size={20} />{/snippet}
  {#snippet action()}
    <Button variant="primary" disabled><Plus size={16} />New project</Button>
  {/snippet}
</EmptyState>

<style>
  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-block-end: var(--space-6);
  }

  h1 {
    margin: 0;
    font-size: var(--text-title);
    font-weight: 500;
  }
</style>
