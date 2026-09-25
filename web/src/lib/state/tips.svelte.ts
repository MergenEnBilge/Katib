import { dismiss, parseTips, shouldShow, TIPS_KEY, type TipState } from '../tour/tips';

function read(): TipState {
  try {
    return parseTips(localStorage.getItem(TIPS_KEY));
  } catch {
    return { seen: [], off: false };
  }
}

function write(state: TipState): void {
  try {
    localStorage.setItem(TIPS_KEY, JSON.stringify(state));
  } catch {
    // Without storage, tips come back the next time the page loads.
  }
}

let state = $state<TipState>(read());

/** Which first-use tips this person has dismissed, kept in the browser. */
export const tips = {
  shouldShow(id: string): boolean {
    return shouldShow(state, id);
  },
  dismiss(id: string): void {
    state = dismiss(state, id);
    write(state);
  },
  get on(): boolean {
    return !state.off;
  },
  setOn(on: boolean): void {
    state = { ...state, off: !on };
    write(state);
  },
  /** Bring every tip back, for someone who wants the hints again. */
  reset(): void {
    state = { seen: [], off: false };
    write(state);
  },
};
