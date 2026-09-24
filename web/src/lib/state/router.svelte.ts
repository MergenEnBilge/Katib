import { matchRoute, type Route } from './router';

let path = $state(location.pathname);

window.addEventListener('popstate', () => {
  path = location.pathname;
});

export const router = {
  get route(): Route {
    return matchRoute(path);
  },
  navigate(to: string): void {
    if (to === path) return;
    history.pushState(null, '', to);
    path = to;
  },
};
