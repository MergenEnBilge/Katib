import { LAYOUT_KEY, OPEN, parseLayout, type Layout } from './layout';

function read(): Layout {
  try {
    return parseLayout(localStorage.getItem(LAYOUT_KEY));
  } catch {
    return OPEN;
  }
}

function write(next: Layout): void {
  try {
    localStorage.setItem(LAYOUT_KEY, JSON.stringify(next));
  } catch {
    // Without storage the choice still holds until the page closes.
  }
}

let current = $state<Layout>(read());

function set(change: Partial<Layout>): void {
  current = { ...current, ...change };
  write(current);
}

/** The panels this person has folded away, kept in the browser. */
export const layout = {
  get sidebar(): boolean {
    return current.sidebar;
  },
  get rail(): boolean {
    return current.rail;
  },
  get panel(): boolean {
    return current.panel;
  },
  get tab(): string {
    return current.tab;
  },
  toggle(which: 'sidebar' | 'rail' | 'panel'): void {
    set({ [which]: !current[which] });
  },
  /** Give the picture the whole window, or put both side panels back. */
  focus(): void {
    const away = current.rail || current.panel;
    set({ rail: !away, panel: !away });
  },
  openTab(tab: string): void {
    set({ tab, panel: false });
  },
};
