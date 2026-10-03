<script lang="ts">
  import { APK_URL } from '../lib/state/phone';

  /** Shown to anyone who scans the share code, so it works before anyone has signed in. */
  const address = $derived(location.origin);
</script>

<main class="get-app">
  <h1>Get Katib</h1>

  <section>
    <h2>Android</h2>
    <p>Tap the button to download the app. When the download finishes, open the file.</p>
    <p class="note">
      Android may ask you to allow installs from this browser the first time. Allow it, then install.
    </p>
    <a class="download" href={APK_URL} download>Download the Android app</a>
    <p class="note">Once it is installed, open Katib and type this address, or scan the code again:</p>
    <p class="address">{address}</p>
  </section>

  <section>
    <h2>iPhone and iPad</h2>
    <p>The app is not on the App Store yet. Open this address in Safari, tap the share button, and
      choose <strong>Add to Home Screen</strong>.</p>
  </section>
</main>

<style>
  .get-app {
    max-width: 32rem;
    margin: 0 auto;
    padding: 2rem 1rem;
    color: var(--text);
    background: var(--surface-1, var(--bg));
    min-height: 100vh;
    font-family: inherit;
  }
  h1 {
    font-size: 1.75rem;
    margin-bottom: 1.5rem;
  }
  h2 {
    font-size: 1.1rem;
    margin: 1.5rem 0 0.5rem;
  }
  .note {
    color: var(--text-2, inherit);
    font-size: 0.9rem;
  }
  .download {
    display: block;
    margin: 1rem 0;
    padding: 0.9rem 1rem;
    border-radius: 10px;
    background: var(--accent);
    color: var(--on-accent);
    text-align: center;
    font-weight: 600;
    text-decoration: none;
  }
  .address {
    font-family: monospace;
    font-size: 1rem;
    word-break: break-all;
    padding: 0.6rem 0.8rem;
    border-radius: 8px;
    background: var(--surface-2, rgba(127, 127, 127, 0.12));
  }
</style>
