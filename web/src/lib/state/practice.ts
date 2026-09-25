import { api, ApiError } from '../api/client';
import { onboarding } from './onboarding.svelte';
import { router } from './router.svelte';
import { toasts } from './toast.svelte';

let busy = false;

/** Make the practice project and open it with the tour running. Reports a problem as a toast. */
export async function startPractice(): Promise<void> {
  if (busy) return;
  busy = true;
  try {
    const project = await api.projects.createSample();
    onboarding.mark('project');
    onboarding.mark('images');
    router.navigate(`/p/${project.id}?tour=1`);
  } catch (err) {
    toasts.show(err instanceof ApiError ? err.message : 'Could not make the practice project.');
  } finally {
    busy = false;
  }
}
