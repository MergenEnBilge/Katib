/** The first things worth doing in Katib, in order. Ticked off as people do them. */
export const STEPS = [
  { id: 'project', title: 'Create a project', hint: 'A project holds one set of pictures and their labels.' },
  { id: 'images', title: 'Add pictures', hint: 'Connect a folder on this computer, or upload from your device.' },
  { id: 'class', title: 'Add a class', hint: 'A class is a kind of thing you label, such as car or cat.' },
  { id: 'shape', title: 'Draw a shape', hint: 'Press B, then drag around something in the picture.' },
  { id: 'done', title: 'Mark a picture done', hint: 'Press Shift+Enter when a picture is finished.' },
  { id: 'export', title: 'Export your labels', hint: 'Get a zip in the format your training code expects.' },
] as const;

export type StepId = (typeof STEPS)[number]['id'];

export interface Progress {
  done: StepId[];
  dismissed: boolean;
}

const KNOWN = new Set<string>(STEPS.map((s) => s.id));

export const STORAGE_KEY = 'katib.onboarding';

/** Read saved progress. Anything unexpected in storage is ignored rather than trusted. */
export function parse(raw: string | null): Progress {
  const empty: Progress = { done: [], dismissed: false };
  if (!raw) return empty;
  try {
    const data = JSON.parse(raw) as { done?: unknown; dismissed?: unknown };
    const done = Array.isArray(data.done)
      ? (data.done.filter((d): d is StepId => typeof d === 'string' && KNOWN.has(d)) as StepId[])
      : [];
    return { done: [...new Set(done)], dismissed: data.dismissed === true };
  } catch {
    return empty;
  }
}

export function complete(progress: Progress, id: StepId): Progress {
  return progress.done.includes(id) ? progress : { ...progress, done: [...progress.done, id] };
}

export function finished(progress: Progress): boolean {
  return STEPS.every((s) => progress.done.includes(s.id));
}
