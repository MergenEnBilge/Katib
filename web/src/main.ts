import { mount } from 'svelte';
import './app.css';
import App from './App.svelte';
import { registerOfflineSupport } from './lib/sync/offline';

const target = document.getElementById('app');
if (!target) throw new Error('Missing #app element in index.html');

registerOfflineSupport();

export default mount(App, { target });
