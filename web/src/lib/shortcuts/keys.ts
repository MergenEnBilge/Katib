/** Default keyboard shortcuts (DESIGN.md section 9). Kept as data so remapping can replace it. */

export type Action =
  | 'tool:select'
  | 'tool:box'
  | 'tool:polygon'
  | 'tool:obb'
  | 'tool:keypoints'
  | 'tool:brush'
  | 'class-picker'
  | 'class-manager'
  | 'prev'
  | 'next'
  | 'done'
  | 'undo'
  | 'redo'
  | 'sync-status'
  | 'hide-all'
  | 'zoom-in'
  | 'zoom-out'
  | 'zoom-fit'
  | 'toggle-rail'
  | 'copy'
  | 'paste'
  | 'help'
  | `class:${number}`;

export interface KeyPress {
  key: string;
  ctrl: boolean;
  shift: boolean;
  alt: boolean;
}

export const SHORTCUT_LIST: { keys: string; action: string; group: string }[] = [
  { group: 'Tools', keys: 'V', action: 'Select' },
  { group: 'Tools', keys: 'B', action: 'Box' },
  { group: 'Tools', keys: 'P', action: 'Polygon' },
  { group: 'Tools', keys: 'O', action: 'Rotated box' },
  { group: 'Tools', keys: 'K', action: 'Keypoints' },
  { group: 'Tools', keys: 'R', action: 'Brush mask' },
  { group: 'Editing', keys: 'E, [ and ]', action: 'Brush: switch to the eraser, change the size' },
  { group: 'Editing', keys: 'V or Delete on a landmark', action: 'Hide it, or remove it' },
  { group: 'Classes', keys: '1 to 9', action: 'Choose a class, or relabel the selection' },
  { group: 'Classes', keys: 'C', action: 'Search classes' },
  { group: 'Classes', keys: 'M', action: 'Class manager' },
  { group: 'Images', keys: 'A or D', action: 'Previous or next image' },
  { group: 'Images', keys: 'Shift + Enter', action: 'Mark as done and go to the next' },
  { group: 'Images', keys: '[', action: 'Collapse or expand the image list' },
  { group: 'Editing', keys: 'Delete', action: 'Delete the selection' },
  { group: 'Editing', keys: 'Arrows', action: 'Nudge by 1 px (Shift for 10 px)' },
  { group: 'Editing', keys: 'Tab', action: 'Select the next shape' },
  { group: 'Editing', keys: 'Ctrl + D', action: 'Duplicate' },
  { group: 'Editing', keys: 'Ctrl + C / V', action: 'Copy and paste shapes' },
  { group: 'Editing', keys: 'Ctrl + Z', action: 'Undo' },
  { group: 'Editing', keys: 'Ctrl + Shift + Z', action: 'Redo' },
  { group: 'Editing', keys: 'Enter', action: 'Close a polygon' },
  { group: 'Editing', keys: 'Esc', action: 'Cancel, then clear the selection' },
  { group: 'View', keys: '+ / - / 0', action: 'Zoom in, out and fit' },
  { group: 'View', keys: 'Space + drag', action: 'Pan' },
  { group: 'View', keys: 'H', action: 'Hide or show all shapes' },
  { group: 'General', keys: 'Ctrl + S', action: 'Show save status' },
  { group: 'General', keys: '?', action: 'Show this list' },
];

/** Turn a key press into an action, or null when the key is not a shortcut. */
export function resolveShortcut(e: KeyPress): Action | null {
  const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;

  if (e.ctrl) {
    if (key === 'z') return e.shift ? 'redo' : 'undo';
    if (key === 'y') return 'redo';
    if (key === 's') return 'sync-status';
    if (key === 'c') return 'copy';
    if (key === 'v') return 'paste';
    return null;
  }
  if (e.alt) return null;

  if (e.shift && key === 'Enter') return 'done';
  if (/^[1-9]$/.test(key)) return `class:${Number(key)}`;

  switch (key) {
    case 'v':
      return 'tool:select';
    case 'b':
      return 'tool:box';
    case 'p':
      return 'tool:polygon';
    case 'o':
      return 'tool:obb';
    case 'k':
      return 'tool:keypoints';
    case 'r':
      return 'tool:brush';
    case 'c':
    case '/':
      return 'class-picker';
    case 'm':
      return 'class-manager';
    case 'a':
      return 'prev';
    case 'd':
      return 'next';
    case 'h':
      return 'hide-all';
    case '+':
    case '=':
      return 'zoom-in';
    case '-':
      return 'zoom-out';
    case '0':
      return 'zoom-fit';
    case '[':
      return 'toggle-rail';
    case '?':
      return 'help';
    default:
      return null;
  }
}
