<script lang="ts">
  import { i18n } from '../../lib/i18n/index.svelte';
  import { theme } from '../../lib/state/theme.svelte';
  import type { ThemePref } from '../../lib/state/theme';

  const themes: { id: ThemePref; label: string }[] = [
    { id: 'system', label: 'Match my device' },
    { id: 'light', label: 'Light' },
    { id: 'dark', label: 'Dark' },
  ];
</script>

<h2>Appearance</h2>
<p class="lead">These choices are kept in this browser, so each person picks their own.</p>

<div class="row">
  <div>
    <p class="name" id="theme-name">Theme</p>
    <p class="help">Katib can follow your device, or stay light or dark.</p>
  </div>
  <div class="options" role="radiogroup" aria-labelledby="theme-name">
    {#each themes as option (option.id)}
      <label class:on={theme.pref === option.id}>
        <input type="radio" name="theme" value={option.id} checked={theme.pref === option.id} onchange={() => theme.set(option.id)} />
        {option.label}
      </label>
    {/each}
  </div>
</div>

<div class="row">
  <div>
    <label class="name" for="language">Language</label>
    <p class="help">
      Katib is ready for more languages. Adding one takes a single file, and the guide in the
      contributing page shows how.
    </p>
  </div>
  <select id="language" value={i18n.locale} onchange={(e) => i18n.setLocale(e.currentTarget.value)}>
    {#each i18n.choices as locale (locale.code)}<option value={locale.code}>{locale.name}</option>{/each}
  </select>
</div>

<style>
  h2 {
    margin: 0 0 var(--space-1);
    font-size: var(--text-title);
  }

  .lead {
    margin: 0;
    color: var(--text-2);
  }

  .row {
    display: grid;
    grid-template-columns: minmax(180px, 1fr) minmax(220px, 1.4fr);
    gap: var(--space-6);
    padding-block: var(--space-4);
    border-block-end: 1px solid var(--border);
  }

  .name {
    margin: 0;
    font-weight: 500;
  }

  .help {
    margin: var(--space-1) 0 0;
    font-size: var(--text-small);
    color: var(--text-2);
  }

  .options {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: start;
  }

  .options label {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    height: var(--h-button);
    padding-inline: var(--space-3);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
    cursor: pointer;
  }

  .options label.on {
    background: var(--accent-muted);
    border-color: var(--accent);
  }

  select {
    height: var(--h-input);
    align-self: start;
    padding-inline: 10px;
    background: var(--bg);
    border: 1px solid var(--border-strong);
    border-radius: var(--radius-control);
  }

  @media (max-width: 699px) {
    .row {
      grid-template-columns: 1fr;
      gap: var(--space-2);
    }
  }
</style>
