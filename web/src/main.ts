import { mount } from 'svelte';
import './app.css';
import App from './App.svelte';

const target = document.getElementById('app');
if (!target) throw new Error('Missing #app element in index.html');

export default mount(App, { target });
