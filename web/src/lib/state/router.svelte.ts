import { matchRoute, type Route } from './router';

let path = $state(location.pathname);

window.addEventListener('popstate', () => {
  path = location.pathname;
});

export const router = {
  get route(): Route {
    return matchRoute(path);
  },
  /** `to` may carry a query string. Routes match on the path alone. */
  navigate(to: string): void {
    if (to === location.pathname + location.search) return;
    history.pushState(null, '', to);
    path = location.pathname;
  },
};
