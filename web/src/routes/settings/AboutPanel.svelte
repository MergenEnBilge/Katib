<script lang="ts">
  import { formatBytes } from '../../lib/format';
  import type { AppSettings } from '../../lib/api/types';

  let { info, shared }: { info: AppSettings['info']; shared: boolean } = $props();

  const rows = $derived([
    ['Version', info.version],
    ['Who uses it', shared ? 'A team, with accounts' : 'Just you, on this computer'],
    ['Database', info.database],
    ['Data folder', info.data_dir],
    ['Space used', formatBytes(info.data_bytes)],
    ['Space free on that drive', formatBytes(info.free_bytes)],
    ['System', `${info.system}, Python ${info.python}`],
  ]);
</script>

<h2>About this Katib</h2>
<p class="lead">Handy to have when you ask for help or check that an upgrade worked.</p>

<dl>
  {#each rows as [name, value] (name)}
    <div>
      <dt>{name}</dt>
      <dd class="mono">{value}</dd>
    </div>
  {/each}
</dl>

<style>
  h2 {
    margin: 0 0 var(--space-1);
    font-size: var(--text-title);
  }

  .lead {
    margin: 0 0 var(--space-4);
    color: var(--text-2);
  }

  dl {
    margin: 0;
  }

  div {
    display: grid;
    grid-template-columns: minmax(180px, 1fr) minmax(220px, 1.4fr);
    gap: var(--space-6);
    padding-block: var(--space-3);
    border-block-end: 1px solid var(--border);
  }

  dt {
    color: var(--text-2);
  }

  dd {
    margin: 0;
    overflow-wrap: anywhere;
  }

  @media (max-width: 699px) {
    div {
      grid-template-columns: 1fr;
      gap: var(--space-1);
    }
  }
</style>
