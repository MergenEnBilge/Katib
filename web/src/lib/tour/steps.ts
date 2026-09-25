/** One stop on the tour. `target` is the value of a `data-tour` attribute, or null for a centered card. */
export interface TourStep {
  id: string;
  target: string | null;
  title: string;
  body: string;
  /** Only shown in projects that use this kind of shape. */
  needs?: string;
  /** The step finishes by itself when the person does this. */
  until?: 'shape';
}

const ALL: TourStep[] = [
  {
    id: 'welcome',
    target: null,
    title: 'Welcome to your workspace',
    body: 'This takes about a minute. You will find the main places and draw your first label. You can leave at any time.',
  },
  {
    id: 'images',
    target: 'images',
    title: 'Your pictures',
    body: 'Every picture in the project is listed here. Click one to open it. The dot on the right shows how far along it is.',
  },
  {
    id: 'classes',
    target: 'classes',
    title: 'Classes',
    body: 'A class is a kind of thing you label. Pick one here, or press its number key. Add your own with the box at the bottom.',
  },
  {
    id: 'tools',
    target: 'tools',
    title: 'Drawing tools',
    body: 'Choose how to mark things. The letter next to each tool is its shortcut, for example B for a box. Press ? any time to see them all.',
  },
  {
    id: 'draw',
    target: 'canvas',
    title: 'Try it: draw a box',
    body: 'Press B, then drag around one of the balls or crates. Katib saves every change as you go, so there is no save button.',
    needs: 'box',
    until: 'shape',
  },
  {
    id: 'done',
    target: 'done',
    title: 'Finish a picture',
    body: 'When a picture is complete, mark it as done. Shift+Enter does it and opens the next one, so you can work without the mouse.',
  },
  {
    id: 'text',
    target: 'text',
    title: 'Words about a picture',
    body: 'Write a caption or any note about the whole picture here. Text can also go inside a shape, from the Details tab.',
    needs: 'text',
  },
  {
    id: 'split',
    target: 'split',
    title: 'Train, validation and test',
    body: 'When you have enough labels, divide the pictures for training. Katib remembers the split and uses it when you export.',
  },
  {
    id: 'export',
    target: 'export',
    title: 'Take your labels with you',
    body: 'Export writes a zip in the format your training code expects, such as YOLO, COCO or JSON Lines.',
  },
  {
    id: 'help',
    target: 'help',
    title: 'Help is always here',
    body: 'Open this menu to replay the tour, see the shortcuts or read the guide. That is everything you need to begin.',
  },
];

/** The steps that make sense for a project that uses these kinds of shape. */
export function tourSteps(types: readonly string[]): TourStep[] {
  return ALL.filter((s) => !s.needs || types.includes(s.needs));
}

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Placement {
  x: number;
  y: number;
}

const GAP = 14;
const MARGIN = 12;

/**
 * Where to put the tour card so it sits beside the highlighted part without covering it, and stays
 * on screen. With no target the card goes in the middle.
 */
export function placeCard(
  target: Rect | null,
  card: { w: number; h: number },
  screen: { w: number; h: number },
): Placement {
  const clampX = (x: number): number => Math.min(Math.max(x, MARGIN), screen.w - card.w - MARGIN);
  const clampY = (y: number): number => Math.min(Math.max(y, MARGIN), screen.h - card.h - MARGIN);
  if (!target) return { x: clampX((screen.w - card.w) / 2), y: clampY((screen.h - card.h) / 2) };

  const fits = {
    right: target.x + target.w + GAP + card.w + MARGIN <= screen.w,
    left: target.x - GAP - card.w - MARGIN >= 0,
    below: target.y + target.h + GAP + card.h + MARGIN <= screen.h,
    above: target.y - GAP - card.h - MARGIN >= 0,
  };
  const centeredY = target.y + target.h / 2 - card.h / 2;
  const centeredX = target.x + target.w / 2 - card.w / 2;
  if (fits.right) return { x: target.x + target.w + GAP, y: clampY(centeredY) };
  if (fits.left) return { x: target.x - GAP - card.w, y: clampY(centeredY) };
  if (fits.below) return { x: clampX(centeredX), y: target.y + target.h + GAP };
  if (fits.above) return { x: clampX(centeredX), y: target.y - GAP - card.h };
  // Nothing fits beside it, as when the target fills the screen. Sit at the bottom.
  return { x: clampX(centeredX), y: clampY(screen.h - card.h - MARGIN) };
}
