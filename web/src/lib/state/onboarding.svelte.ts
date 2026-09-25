import { complete, finished, parse, STEPS, STORAGE_KEY, type Progress, type StepId } from './onboarding';

function read(): Progress {
  try {
    return parse(localStorage.getItem(STORAGE_KEY));
  } catch {
    return { done: [], dismissed: false };
  }
}

function write(progress: Progress): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(progress));
  } catch {
    // Without storage the checklist still works until the page closes.
  }
}

let progress = $state<Progress>(read());

/** Which of the first steps this person has done, kept in the browser. */
export const onboarding = {
  steps: STEPS,
  isDone(id: StepId): boolean {
    return progress.done.includes(id);
  },
  mark(id: StepId): void {
    const next = complete(progress, id);
    if (next === progress) return;
    progress = next;
    write(progress);
  },
  get count(): number {
    return progress.done.length;
  },
  get finished(): boolean {
    return finished(progress);
  },
  get visible(): boolean {
    return !progress.dismissed && !finished(progress);
  },
  dismiss(): void {
    progress = { ...progress, dismissed: true };
    write(progress);
  },
  show(): void {
    progress = { ...progress, dismissed: false };
    write(progress);
  },
};
