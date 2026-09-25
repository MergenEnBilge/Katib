/**
 * Short, practical hints that appear the first time someone reaches a tool, window or page.
 * Each has an id like `tool:polygon`. Once dismissed a tip stays away, and a switch turns them all off.
 */
export interface Tip {
  title: string;
  body: string;
  /** Things worth knowing, one line each. */
  points?: string[];
  /** Shortcuts that belong to this place. */
  keys?: { keys: string; does: string }[];
}

export const TIPS: Record<string, Tip> = {
  'tool:select': {
    title: 'Select and edit',
    body: 'Click a shape to pick it up. Everything you change saves by itself.',
    points: [
      'Drag a shape to move it, or drag one of its handles to resize it.',
      'Drag across empty space to pick several shapes at once.',
      'Locked classes cannot be edited and hidden classes cannot be picked. Use the eye and lock beside each class.',
    ],
    keys: [
      { keys: 'Tab', does: 'Next shape' },
      { keys: 'Arrows', does: 'Nudge (Shift for 10 px)' },
      { keys: '1 to 9', does: 'Relabel the selection' },
      { keys: 'Ctrl+D', does: 'Duplicate' },
      { keys: 'Delete', does: 'Remove' },
    ],
  },
  'tool:box': {
    title: 'Drawing boxes',
    body: 'Pick a class first, then drag from one corner of the object to the opposite corner.',
    points: [
      'A tiny accidental drag is ignored, so a stray click will not leave a speck behind.',
      'Draw close to the edge of the object. Zoom in with + for small things.',
      'Press Esc while dragging to cancel.',
    ],
    keys: [
      { keys: 'B', does: 'Box tool' },
      { keys: '1 to 9', does: 'Choose the class' },
      { keys: 'Ctrl+Z', does: 'Undo' },
    ],
  },
  'tool:polygon': {
    title: 'Drawing polygons',
    body: 'Click around the outline of the object, one point at a time.',
    points: [
      'Close the shape by pressing Enter or by clicking the first point again.',
      'Put more points on curves and fewer on straight edges.',
      'After closing, drag a point to fix it. Nothing is lost if you slip.',
    ],
    keys: [
      { keys: 'P', does: 'Polygon tool' },
      { keys: 'Enter', does: 'Close the shape' },
      { keys: 'Esc', does: 'Cancel this shape' },
    ],
  },
  'tool:wand': {
    title: 'Magic wand',
    body: 'Click inside an object and Katib outlines the area of similar color as a polygon.',
    points: [
      'It works best on objects that stand out from their background.',
      'If it picks too little, make the colors count as more alike. If it picks too much, make them less alike.',
      'The result is an ordinary polygon, so you can tidy it afterward.',
    ],
    keys: [
      { keys: 'W', does: 'Magic wand' },
      { keys: '[ and ]', does: 'Less or more alike' },
    ],
  },
  'tool:obb': {
    title: 'Rotated boxes',
    body: 'For things that sit at an angle, such as ships seen from above or a line of text.',
    points: [
      'Drag along one edge of the object, then move outward to the other side and click.',
      'Afterward, drag the round handle to turn the box.',
    ],
    keys: [{ keys: 'O', does: 'Rotated box tool' }],
  },
  'tool:keypoints': {
    title: 'Keypoints',
    body: 'Click each landmark in the order the class lists them, such as nose, then left eye.',
    points: [
      'Landmarks belong to the class. Set them under Class manager before you start.',
      'Shift+click marks a landmark as hidden, for example behind an object.',
      'Press N to skip a landmark you cannot see. Press Enter to finish early.',
    ],
    keys: [
      { keys: 'K', does: 'Keypoints tool' },
      { keys: 'N', does: 'Skip this landmark' },
      { keys: 'Enter', does: 'Finish' },
    ],
  },
  'tool:brush': {
    title: 'Brush masks',
    body: 'Paint over the area. Good for shapes that are hard to outline, like smoke or a road.',
    points: [
      'Painting is on a coarse grid, which keeps masks small and fast. Zoom in for finer work.',
      'Switch to the eraser to take paint back.',
    ],
    keys: [
      { keys: 'R', does: 'Brush' },
      { keys: 'E', does: 'Eraser' },
      { keys: '[ and ]', does: 'Brush size' },
    ],
  },
  'panel:classes': {
    title: 'Classes and tags',
    body: 'A class is a kind of thing you label. The one that is highlighted is the one you draw with.',
    points: [
      'Add a class with the box at the bottom, or press M for the class manager, where you can rename, merge and delete them.',
      'Renaming a class updates every shape. Merges and deletes show you what they will touch first, and can be undone for 30 days.',
    ],
  },
  'panel:details': {
    title: 'Details of a shape',
    body: 'Select a shape to see its class, its exact numbers and any attributes you defined.',
    points: ['Type in the position and size boxes for pixel-exact changes.', 'Select several shapes to relabel or delete them together.'],
  },
  'panel:text': {
    title: 'Writing about a picture',
    body: 'Add a caption or a note about the whole image. You can add as many as you like.',
    points: [
      'Each entry can carry an optional label, such as caption or question.',
      'Text saves when you click away from the box.',
      'To write the words inside a shape, select the shape and use the Details tab.',
    ],
  },
  'panel:review': {
    title: 'Review',
    body: 'Comments belong to an image and can be resolved. Reviewers approve finished images or send them back.',
    points: ['Turn review on for the project under Team.', 'The Inbox lists what needs your attention.'],
  },
  'dialog:import': {
    title: 'Bringing in pictures and labels',
    body: 'Add the pictures first. Then import label files that match them by filename.',
    points: [
      'A connected folder is read where it is. Katib never copies, moves or changes your originals.',
      'Press the refresh button beside a folder to pick up new photos later.',
      'If your dataset already has train, val and test folders, Katib keeps that split.',
    ],
  },
  'dialog:export': {
    title: 'Exporting',
    body: 'Pick the format your training code expects, then which pictures to include.',
    points: [
      'If your pictures have a saved split, the export uses it. You can also make a fresh one just for this export.',
      'YOLO numbers classes by their position. Katib warns you if the order changed since the last export.',
      'Turn on "Include the image files" to get a folder you can train from as it is.',
    ],
  },
  'dialog:splits': {
    title: 'Train, validation and test',
    body: 'Training images teach the model, validation images check progress, and test images are held back for the end.',
    points: [
      'Pick the kind of dataset for a sensible starting ratio, then change it as you like.',
      'The same seed always gives the same split. Try a new shuffle for a different one.',
      'Turn on "keep rare classes in every split" if some classes have few examples.',
      'The preview tells you how many images would move before anything changes.',
    ],
  },
  'dialog:prelabel': {
    title: 'Pre-labeling with a model',
    body: 'A model you provide drafts boxes. You correct them, which is faster than drawing from nothing.',
    points: [
      'Drafts are drawn dashed and show the model’s confidence.',
      'Start with a higher confidence to get fewer, more reliable boxes.',
      'The whole run can be undone from History.',
    ],
  },
  'dialog:classes': {
    title: 'Class manager',
    body: 'Rename, recolor, reorder, merge or delete classes, and define landmarks and attributes.',
    points: ['Every bulk change shows what it will touch, and can be undone from History.'],
  },
  'dialog:history': {
    title: 'History',
    body: 'Bulk changes such as merges, deletes, pre-labeling and split shuffles are listed here.',
    points: ['Undo restores what you had. Shapes edited since are left as they are and counted.'],
  },
  'dialog:health': {
    title: 'Dataset health',
    body: 'Checks for problems that quietly hurt training.',
    points: ['Tiny shapes, duplicates, near-identical photos and lopsided classes are listed with links to fix them.'],
  },
  'dialog:team': {
    title: 'Working together',
    body: 'Invite people with a link and give each a role.',
    points: [
      'A link works once and expires after seven days. Send it only to the person you are inviting.',
      'Viewers can look, annotators can draw, reviewers can approve, managers can import and export.',
    ],
  },
  'page:gallery': {
    title: 'Class gallery',
    body: 'Every shape of a class as a small crop, side by side. Mistakes stand out.',
    points: ['Select several crops, then relabel or delete them together. Both can be undone.'],
  },
  'page:inbox': {
    title: 'Inbox',
    body: 'Images assigned to you and images sent back for changes.',
  },
  'settings:sharing': {
    title: 'Sharing',
    body: 'Choose accounts before letting anyone else in.',
    points: ['Changes marked “Needs a restart” wait until you press Restart Katib now.'],
  },
  'settings:storage': {
    title: 'Storage',
    body: 'Your projects live in the data folder. Katib may only read folders listed here.',
    points: ['Changing the data folder does not move what is already there. Copy it first.'],
  },
  'settings:limits': {
    title: 'Limits',
    body: 'Keep uploads and undo history in check. These apply as soon as you save.',
  },
  'settings:model': {
    title: 'Model help',
    body: 'Turn on pre-labeling, then put your .onnx files in the models folder.',
  },
};

export interface TipState {
  seen: string[];
  off: boolean;
}

export const TIPS_KEY = 'katib.tips';

/** Read saved tip progress. Anything unexpected is ignored rather than trusted. */
export function parseTips(raw: string | null): TipState {
  const empty: TipState = { seen: [], off: false };
  if (!raw) return empty;
  try {
    const data = JSON.parse(raw) as { seen?: unknown; off?: unknown };
    const seen = Array.isArray(data.seen) ? data.seen.filter((s): s is string => typeof s === 'string' && s in TIPS) : [];
    return { seen: [...new Set(seen)], off: data.off === true };
  } catch {
    return empty;
  }
}

export function shouldShow(state: TipState, id: string): boolean {
  return !state.off && id in TIPS && !state.seen.includes(id);
}

export function dismiss(state: TipState, id: string): TipState {
  return state.seen.includes(id) ? state : { ...state, seen: [...state.seen, id] };
}
