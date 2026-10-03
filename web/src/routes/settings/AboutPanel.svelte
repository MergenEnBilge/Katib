<script lang="ts">
  import { api } from '../../lib/api/client';
  import type { AppSettings } from '../../lib/api/types';
  import { AUTHOR, AUTHOR_URL, REPO_URL } from '../../lib/credit';
  import { formatBytes } from '../../lib/format';

  /** `info` is only there for administrators; everyone else still gets the version and credit. */
  let { info = null, shared }: { info?: AppSettings['info'] | null; shared: boolean } = $props();

  let version = $state('');

  $effect(() => {
    if (info) return;
    api
      .server()
      .then((h) => (version = h.version))
      .catch(() => (version = ''));
  });

  const rows = $derived(
    info
      ? [
          ['Version', info.version],
          ['Who uses it', shared ? 'A team, with accounts' : 'Just you, on this computer'],
          ['Database', info.database],
          ['Data folder', info.data_dir],
          ['Space used', formatBytes(info.data_bytes)],
          ['Space free on that drive', formatBytes(info.free_bytes)],
          ['System', `${info.system}, Python ${info.python}`],
          ...(info.log_dir ? [['Server log', info.log_dir]] : []),
        ]
      : version
        ? [['Version', version]]
        : [],
  );
</script>

<h2>About this Katib</h2>

<div class="credit">
  <p>
    Built by <a href={AUTHOR_URL} target="_blank" rel="noopener noreferrer">{AUTHOR}</a>.
  </p>
  <p>
    <a href={REPO_URL} target="_blank" rel="noopener noreferrer">Source on GitHub</a>, under the MIT licence.
  </p>
</div>

{#if info}
  <p class="lead">Handy to have when you ask for help or check that an upgrade worked.</p>
{/if}

<dl>
  {#each rows as [name, value] (name)}
    <div class="row">
      <dt>{name}</dt>
      <dd class="mono">{value}</dd>
    </div>
  {/each}
</dl>

<style>
  h2 {
    margin: 0 0 var(--space-3);
    font-size: var(--text-title);
  }

  .credit {
    margin-block-end: var(--space-4);
    padding: var(--space-3) var(--space-4);
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: var(--radius-group);
  }

  .credit p {
    margin: 0;
  }

  .credit p + p {
    margin-block-start: var(--space-1);
    color: var(--text-2);
    font-size: var(--text-small);
  }

  .credit a {
    color: var(--accent-text);
  }

  .lead {
    margin: 0 0 var(--space-4);
    color: var(--text-2);
  }

  dl {
    margin: 0;
  }

  .row {
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
    .row {
      grid-template-columns: 1fr;
      gap: var(--space-1);
    }
  }
</style>
