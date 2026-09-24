export interface Toast {
  message: string;
  action?: { label: string; run: () => void };
}

const VISIBLE_MS = 6000;

let current = $state<Toast | null>(null);
let timer: ReturnType<typeof setTimeout> | undefined;

function arm(): void {
  clearTimeout(timer);
  timer = setTimeout(() => (current = null), VISIBLE_MS);
}

/** One toast at a time. A new one replaces the old. */
export const toasts = {
  get current(): Toast | null {
    return current;
  },
  show(message: string, action?: Toast['action']): void {
    current = { message, action };
    arm();
  },
  hold(): void {
    clearTimeout(timer);
  },
  release(): void {
    if (current) arm();
  },
  dismiss(): void {
    clearTimeout(timer);
    current = null;
  },
};
