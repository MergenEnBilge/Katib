/** One stop on a tour. `target` is the value of a `data-tour` attribute, or null for a centered card. */
export interface TourStep {
  id: string;
  target: string | null;
  title: string;
  body: string;
  /** Only shown when this is true of the person's situation. */
  when?: (ctx: TourContext) => boolean;
  /** The step finishes by itself when the person does this. */
  until?: 'shape';
}

/** What is true right now, so a tour can skip what does not apply and point at what does. */
export interface TourContext {
  types: readonly string[];
  hasImages: boolean;
  hasClasses: boolean;
  canManage: boolean;
  shared: boolean;
}

const uses = (type: string) => (ctx: TourContext) => ctx.types.includes(type);

const WORKSPACE: TourStep[] = [
  {
    id: 'welcome',
    target: null,
    title: 'Welcome to your workspace',
    body: 'This takes about a minute. You will find the main places and draw your first label. You can leave at any time.',
  },
  {
    id: 'add-pictures',
    target: 'import',
    title: 'Start by adding pictures',
    body: 'This project has no pictures yet. Choose Import to connect a folder on this computer or upload from your device. Katib only reads your folder and never changes the originals.',
    when: (ctx) => !ctx.hasImages,
  },
  {
    id: 'images',
    target: 'images',
    title: 'Your pictures',
    body: 'Every picture in the project is listed here. Click one to open it. The dot on the right shows how far along it is, and you can filter by status or split above.',
    when: (ctx) => ctx.hasImages,
  },
  {
    id: 'add-class',
    target: 'class-input',
    title: 'Make your first class',
    body: 'A class is a kind of thing you label, such as car or cat. Type a name here and press Enter. The first class is picked for you.',
    when: (ctx) => !ctx.hasClasses,
  },
  {
    id: 'classes',
    target: 'classes',
    title: 'Classes',
    body: 'The highlighted class is the one you draw with. Pick another here or press its number key. Add more with the box at the bottom, and press M to rename, merge or delete classes.',
    when: (ctx) => ctx.hasClasses,
  },
  {
    id: 'tools',
    target: 'tools',
    title: 'Drawing tools',
    body: 'Choose how to mark things. The letter next to each tool is its shortcut, for example B for a box. Only the shapes this project uses appear. Press ? any time to see every shortcut.',
  },
  {
    id: 'draw',
    target: 'canvas',
    title: 'Try it: draw a box',
    body: 'Press B, pick a class, then drag around one of the objects. Katib saves every change as you go, so there is no save button. Undo with Ctrl+Z.',
    when: uses('box'),
    until: 'shape',
  },
  {
    id: 'done',
    target: 'done',
    title: 'Finish a picture',
    body: 'When a picture is complete, mark it as done. Shift+Enter does it and opens the next one, so you can work without the mouse. Finished pictures count toward the progress on the home page.',
  },
  {
    id: 'text',
    target: 'text',
    title: 'Words about a picture',
    body: 'Write a caption or any note about the whole picture here. To write the words inside a shape, select the shape and use the Details tab.',
    when: uses('text'),
  },
  {
    id: 'split',
    target: 'split',
    title: 'Train, validation and test',
    body: 'When you have enough labels, divide the pictures for training. Katib keeps the split on each image and uses it when you export. If your dataset came with a split, it is already here.',
    when: (ctx) => ctx.canManage,
  },
  {
    id: 'team',
    target: 'team',
    title: 'Invite your team',
    body: 'Create an invite link and give each person a role, from viewer to manager. Katib hands each annotator the next image and shows who else is working.',
    when: (ctx) => ctx.shared && ctx.canManage,
  },
  {
    id: 'export',
    target: 'export',
    title: 'Take your labels with you',
    body: 'Export writes a zip in the format your training code expects, such as YOLO, COCO or JSON Lines, using your saved split.',
    when: (ctx) => ctx.canManage,
  },
  {
    id: 'help',
    target: 'help',
    title: 'Help is always here',
    body: 'Open this menu to replay this tour, take a tour of the other screens, see the shortcuts or read the guide. Small tips also appear the first time you use a new tool.',
  },
];

const HOME: TourStep[] = [
  {
    id: 'home-welcome',
    target: null,
    title: 'Your projects',
    body: 'Everything you label lives in a project: a set of pictures, their classes and their labels. This is where you find them.',
  },
  {
    id: 'home-new',
    target: 'new-project',
    title: 'Start a project',
    body: 'Choose New project, name it and pick the kinds of shapes you will draw. Press N as a shortcut. Pick only what you need. You can only save the shapes you choose.',
  },
  {
    id: 'home-search',
    target: 'search',
    title: 'Find one quickly',
    body: 'Type part of a name to narrow the list. Each card shows how many pictures are done.',
  },
  {
    id: 'home-inbox',
    target: 'nav-inbox',
    title: 'Your inbox',
    body: 'Pictures assigned to you and pictures sent back for changes land here.',
    when: (ctx) => ctx.shared,
  },
  {
    id: 'home-settings',
    target: 'nav-settings',
    title: 'Settings',
    body: 'Everything about how Katib runs is here, each with a plain explanation: sharing, storage, limits and backups.',
  },
  {
    id: 'home-help',
    target: 'nav-help',
    title: 'Help',
    body: 'Come back here for tours of any screen, a practice project, and links to the guide.',
  },
];

const SETTINGS: TourStep[] = [
  {
    id: 'settings-welcome',
    target: null,
    title: 'Settings',
    body: 'You never have to edit a file. Every option has a short explanation, and Katib checks what you type before it saves.',
  },
  {
    id: 'settings-tabs',
    target: 'settings-tabs',
    title: 'Sections',
    body: 'Sharing decides who can reach Katib. Storage says where your data lives. Limits and Model help fine-tune it. Backup makes a copy you can keep elsewhere.',
  },
  {
    id: 'settings-restart',
    target: 'settings-body',
    title: 'Applies now or after a restart',
    body: 'Each setting says which it is. When some are waiting, a Restart Katib now button appears at the top and does it for you.',
  },
  {
    id: 'settings-save',
    target: 'settings-save',
    title: 'Save your changes',
    body: 'Changes are kept here until you save. Discard puts everything back the way it was.',
  },
];

export type TourName = 'workspace' | 'home' | 'settings';

const BY_NAME: Record<TourName, TourStep[]> = { workspace: WORKSPACE, home: HOME, settings: SETTINGS };

/** The steps of a tour that make sense for this situation. */
export function tourSteps(name: TourName, ctx: TourContext): TourStep[] {
  return BY_NAME[name].filter((s) => !s.when || s.when(ctx));
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
