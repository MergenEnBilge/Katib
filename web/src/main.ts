import { mount } from 'svelte';
import './app.css';
import App from './App.svelte';
import { registerOfflineSupport } from './lib/sync/offline';

const target = document.getElementById('app');
if (!target) throw new Error('Missing #app element in index.html');

registerOfflineSupport();
// The page ships with a logo and spinner so it is not blank while scripts load. The app replaces it.
target.replaceChildren();

export default mount(App, { target });
