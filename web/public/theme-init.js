// Runs before first paint so a light preference does not flash dark.
// Kept as a separate file so a strict Content-Security-Policy can block inline scripts.
try {
  var pref = localStorage.getItem('katib.theme') || 'system';
  var light = pref === 'light' || (pref === 'system' && matchMedia('(prefers-color-scheme: light)').matches);
  document.documentElement.dataset.theme = light ? 'light' : 'dark';
} catch {
  /* storage blocked: keep the dark default */
}
