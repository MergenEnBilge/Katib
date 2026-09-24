# Katib design

How Katib looks and behaves. The visual direction comes from `KATIB_Prototype.html` (keep a copy in `docs/design/`). This file is the source of truth for tokens and rules. Where the prototype and this file disagree, this file wins, and the differences are listed in [Changes from the prototype](#15-changes-from-the-prototype).

## Contents

1. [Principles](#1-principles)
2. [Color](#2-color)
3. [Typography](#3-typography)
4. [Spacing, size and layout](#4-spacing-size-and-layout)
5. [Motion](#5-motion)
6. [Components](#6-components)
7. [Patterns](#7-patterns)
8. [Annotation canvas](#8-annotation-canvas)
9. [Keyboard shortcuts](#9-keyboard-shortcuts)
10. [Responsive and touch](#10-responsive-and-touch)
11. [Accessibility](#11-accessibility)
12. [Icons](#12-icons)
13. [Writing UI text](#13-writing-ui-text)
14. [Screens](#14-screens)
15. [Changes from the prototype](#15-changes-from-the-prototype)

---

## 1. Principles

- **Calm and dense.** Neutral surfaces, one accent, thin borders. The image is the loudest thing on screen.
- **Keyboard first, mouse friendly.** Every frequent action has a shortcut and shows it in its tooltip.
- **Say what will happen.** Buttons and dialogs use real counts and plain words ("12 annotations on 4 images will be relabeled").
- **Reversible.** Destructive actions preview, confirm when large, and offer Undo afterward.
- **No surprises.** Nothing moves or changes unless the user did something. State is always visible: saved or not, who is on this image, what tool is active.
- **One way to do each thing.** Reuse the same component and pattern everywhere.
- **Nothing decorative.** No gradients, no illustrations, no animation for its own sake.

## 2. Color

Dark is the default theme. Light is fully supported. The theme is set with `data-theme="dark|light"` on `<html>`, and "System" follows `prefers-color-scheme`.

Use the variables below. Never hardcode a hex value in a component.

### Tokens

| Token | Role | Dark | Light |
|-------|------|------|-------|
| `--bg` | App background, inputs | `#0B0E0C` | `#FFFFFF` |
| `--surface-1` | Sidebars, panels, cards | `#141814` | `#F6F8F5` |
| `--surface-2` | Menus, modals, tooltips, toasts, selected tabs | `#1B211C` | `#FFFFFF` |
| `--border` | Default dividers and outlines | `#2A322B` | `#E1E6E0` |
| `--border-strong` | Hover borders, floating surfaces, form controls | `#3B453C` | `#C7CFC5` |
| `--text` | Primary text | `#EDEFEA` | `#161A16` |
| `--text-2` | Secondary text, inactive icons | `#A3AEA5` | `#535B52` |
| `--text-3` | Hints, metadata, placeholders | `#808B81` | `#6B746A` |
| `--accent` | Primary actions, active states, progress | `#2FA366` | `#1F7A4C` |
| `--accent-hover` | Hover on accent | `#3ABF79` | `#186A40` |
| `--accent-muted` | Selected row and active tool background | `#173B27` | `#E6F2EA` |
| `--on-accent` | Text on accent | `#06140C` | `#FFFFFF` |
| `--danger` | Destructive actions, errors | `#E0574B` | `#C7392E` |
| `--danger-muted` | Danger callout background | `#2E1714` | `#FBEAE8` |
| `--on-danger` | Text on danger | `#1A0806` | `#FFFFFF` |
| `--warning` | Pending or unsaved state (dots, icons) | `#D9A441` | `#B4832A` |
| `--warning-text` | Warning used as text | `#D9A441` | `#8A6212` |
| `--image-bg` | Behind images and empty thumbnails | `#191E1A` | `#EEF1ED` |
| `--stripe` | Placeholder stripe pattern | `rgba(237,239,234,.045)` | `rgba(22,26,22,.055)` |
| `--scrim` | Modal backdrop | `rgba(0,0,0,.6)` | `rgba(22,26,22,.28)` |
| `--shadow` | Floating surfaces only | `0 12px 32px rgba(0,0,0,.45)` | `0 12px 32px rgba(22,26,22,.12)` |

Mapping from the prototype's short names: `--s1` to `--surface-1`, `--s2` to `--surface-2`, `--bd` to `--border`, `--bds` to `--border-strong`, `--t1/t2/t3` to `--text`, `--text-2`, `--text-3`, `--ac/ach/acm/onac` to `--accent`, `--accent-hover`, `--accent-muted`, `--on-accent`, `--dg/dgm/ondg` to `--danger`, `--danger-muted`, `--on-danger`, `--wn` to `--warning`, `--img` to `--image-bg`, `--sh` to `--shadow`.

### Use of color

- **One accent.** Green marks the primary action, the selected item, progress and "saved". Do not add a second accent.
- **Selection** is `--accent-muted` background, plus `--text` for the label. Not a border alone.
- **Danger** is reserved for destructive actions and errors. A destructive button sits in a secondary style with danger text until the final confirm, which is solid `--danger`.
- **Class colors** are the only place multiple hues appear. They belong to data, not to the interface.
- **Status is never color alone.** See the status dot in section 6.

### Class palette

Ten defaults, assigned in order. They are readable on dark and light image backgrounds, and dark label text (`#0B0E0C`) passes 5:1 on every one.

```
#4C8DF6  #8B6CF0  #E86FB0  #F2994A  #2EC4D6
#F2C94C  #D16BF0  #5B7CFA  #FF8A65  #7FB3FF
```

Beyond ten classes, generate colors by rotating hue in steps of about 137 degrees (golden angle) at fixed saturation and lightness, and skip any that is within a small distance of an existing class color. Users can pick any color. The picker offers the ten defaults first, then a full color input.

Users can turn on **pattern mode**, which adds a dash style per class to outlines (solid, dashed, dotted, dash-dot) so classes can be told apart without relying on color.

## 3. Typography

| Use | Font |
|-----|------|
| Interface | **Inter** |
| Filenames, paths, numbers, counts, geometry, keycaps | **JetBrains Mono** |

Both fonts are **bundled with the app** as self-hosted `woff2` files. Do not load them from a CDN: Katib runs offline on LANs and desktops. Use the variable version of Inter. Subset to Latin, Latin Extended, Cyrillic and Greek by default, and load other scripts on demand.

The prototype references JetBrains Mono but does not embed it. Bundle it.

Weights: 400 for body, 500 for labels, buttons and titles, 700 only for the logo mark and large stat numbers.

| Role | Size | Weight | Notes |
|------|------|--------|-------|
| Page title | 20 px | 500 | Projects, Inbox |
| Section or dialog title | 15 px | 500 | Card titles, dialog titles, empty-state titles |
| Body | 13 px | 400 | Line height 1.4 |
| Secondary | 12 px | 400 | Metadata, descriptions under titles |
| Overline | 11 px | 500 | Uppercase, `letter-spacing: .06em`, `--text-3` |
| Mono small | 11 px | 400 | Paths, counts, keycaps |
| Mono body | 12 px | 400 | Filenames, geometry values |

Sentence case everywhere except the overline style. Use `text-wrap: pretty` on paragraphs. Truncate long names with an ellipsis and give them a tooltip.

Numbers that change (counts, zoom, coordinates) use tabular figures (`font-variant-numeric: tabular-nums`) so they do not jitter.

## 4. Spacing, size and layout

Base unit 4 px. Common steps: 4, 8, 12, 16, 24, 32.

### Control heights (desktop density)

| Height | Use |
|--------|-----|
| 22 px | Filter chips |
| 24 px | Small icon buttons, class chips in the Details panel |
| 28 px | Icon buttons, toolbar buttons, segmented tools |
| 30 px | Secondary buttons in dialogs, panel search inputs |
| 32 px | Primary buttons, list rows, menu items, search field |
| 34 px | Form inputs in dialogs |
| 44 px | Empty-state icon tile (40 in panels) |

On touch devices, every interactive target grows to at least 40 px (see section 10).

### Radius

| Radius | Use |
|--------|-----|
| 3 px | Class swatch, label tag on shapes |
| 4 px | Chips, keycaps, small tags |
| 6 px | Buttons, inputs, list rows, tools |
| 8 px | Segmented tool group container |
| 10 px | Cards, menus, modals, toasts, callouts |

### Borders and elevation

Surfaces are separated by 1 px `--border` lines, not shadows. `--shadow` is only for things that float: menus, modals, tooltips, toasts.

### Layout dimensions

| Element | Size |
|---------|------|
| Home sidebar | 280 px wide, header 56 px |
| Workspace header | 48 px |
| Workspace left rail | 280 px (56 px when collapsed) |
| Workspace right panel | 280 px |
| Panel header (tabs) | 45 px |
| Project card grid | `repeat(auto-fill, minmax(260px, 1fr))`, gap 16 |
| Page padding | 32 px |
| Form dialog | 460 px wide |
| Confirm dialog | 440 px wide |
| Class manager | 880 x 600 px, max 100% of the viewport minus 48 px |
| Toast | Max 640 px, 20 px from the bottom, centered |

### Z-order

Menu backdrop 40, menu 50, modal 60, toast 80, tooltip 90, top progress bar 100.

## 5. Motion

- Hover and color changes: `140ms ease-out`.
- Top progress bar: 2 px, `--accent`, eases to 85% during a job and completes on finish.
- Toasts and dialogs appear without animation, or with a 120 ms fade.
- No other animation. Nothing bounces, slides or pulses.
- Respect `prefers-reduced-motion`: remove the fade and the progress easing.

## 6. Components

Sizes above apply. All components have hover, focus-visible, active and disabled states. Disabled is `opacity: .4` with `pointer-events: none`.

**Button, primary.** 32 px, `--accent` background, `--on-accent` text, weight 500, radius 6, padding 0 12 px (10 px on the icon side). Hover: `--accent-hover`.

**Button, secondary.** 30 to 32 px, transparent, 1 px `--border`, weight 500. Hover: `--border-strong` border and `--surface-1` background.

**Button, ghost.** No border. Text `--text-2`. Hover: `--surface-2` background and `--text`. Used in headers and rails.

**Button, danger.** Secondary style with `--danger` text. The final confirm button is solid `--danger` with `--on-danger` text.

**Icon button.** 28 px square (24 px in dense areas), radius 6, `--text-2`. Always has a tooltip and an `aria-label`.

**Input.** 34 px in dialogs, 30 px in panels, 32 px for search fields. `--bg` background, 1 px `--border-strong` border, radius 6. Focus shows the focus ring (section 11). Search fields have a 16 px icon 10 px from the left and 32 px of left padding.

**Segmented tool group.** 2 px padding inside a `--bg` container with 1 px border and radius 8. Buttons are 30 x 28. The active tool has `--accent-muted` background and `--accent` icon.

**Chip (filter).** 22 px, radius 4, 11 px text, 1 px border. Active: `--accent-muted` fill and border, `--text` label. Shows a count.

**Class chip.** 24 px, radius 4, 12 px text, color square (10 px) then name. Selected: `--accent` border and `--accent-muted` fill.

**List row.** 32 px, radius 6, padding 0 8. Selected: `--accent-muted` background and `--text`. Hover: `--surface-2`. Used for classes, menu items, merge targets.

**Class row.** List row with a 10 px rounded color swatch, name (truncated), annotation count in mono 11 px, and a keycap showing the 1 to 9 shortcut where one exists.

**Image row (filmstrip).** 48 x 32 thumbnail with 1 px border, filename in mono 12 px, meta in 11 px `--text-3`, and a status dot on the right.

**Status dot.** 9 px circle with a 1.5 px border. Three states that also differ in shape, not only color:
- Unlabeled: hollow, `--text-3` border
- In progress: hollow, `--accent` border
- Done: filled `--accent`
- Approved: filled `--accent` with a small check
- Rejected: filled `--danger`

**Card (project).** `--surface-1`, 1 px border, radius 10. 128 px cover area with the stripe pattern (or the first image as a thumbnail), then title 15/500, meta 12 px `--text-2`, a 4 px progress bar, and "N of M done" with the last-edited time. Hover: `--border-strong`.

**Progress bar.** 4 px tall, `--border` track, `--accent` fill, radius 2.

**Toggle.** 28 x 16 track, 12 px white knob, `--accent` track when on, `--border-strong` when off.

**Radio row.** 14 px circle with a 6 px dot, used for single-choice lists like merge targets.

**Checkbox tile.** 16 px box with radius 4, filled `--accent` with a 12 px check.

**Keycap.** Mono 11 px, `--text-3`, 1 px border, radius 4, 18 px minimum width.

**Tooltip.** 26 px tall, `--surface-2`, 1 px `--border-strong`, radius 6, `--shadow`, 12 px text, optional keycap. Appears below the element (right of it in the collapsed rail), flips at screen edges. Delay 400 ms. Also appears on keyboard focus.

**Menu.** 200 to 260 px wide, `--surface-2`, 1 px border, radius 10, `--shadow`, 4 px padding. Items are 32 px rows. Separators are 1 px `--border` with 2 px margin. Overline group headings. Danger items are red text with a `--danger-muted` hover.

**Modal.** Centered on a `--scrim` backdrop. `--surface-2`, 1 px border, radius 10, `--shadow`. Header 20 px padding, title 15/500 with a 12 to 13 px description. Footer has a top border, right-aligned buttons, Cancel first, primary last. Escape and backdrop click close it, unless it holds unsaved input, in which case Escape closes only the current step.

**Toast.** Bottom center, `--surface-2`, 1 px `--border-strong`, radius 10, `--shadow`. Message, then an optional text button in `--accent` ("Undo"). Visible for about 6 seconds, and stays while hovered or focused. Announced through `aria-live="polite"`. Only one at a time: a new toast replaces the old.

**Callout.** Radius 10, 14 x 16 padding. Neutral: `--surface-1` and `--border`. Danger: `--danger-muted` background and `--danger` border.

**Empty state.** Dashed `--border-strong` outline (10 px radius) for page-level, none for panels. A 44 px icon tile (`--surface-1`, 1 px border, radius 10), a 15/500 title, one or two sentences in `--text-2` (max width about 380 px), and one primary action.

**Save indicator.** In the workspace header: an 8 px dot and a label. `--accent` "Saved", `--warning` "Saving...", `--warning` "3 pending" when offline. Clicking it opens sync details.

## 7. Patterns

### Destructive actions

1. The trigger is a secondary button with danger text and an ellipsis when it opens a dialog ("Delete class...").
2. The dialog leads with a preview in a danger callout: "This will remove 1,204 annotations from 312 images in Street Scenes."
3. State consequences that are not obvious ("Sub-classes move to the top level", "Attribute values that Car does not define are dropped").
4. For large or permanent actions (delete class, delete project), require typing the name to confirm.
5. After confirming, show a toast with counts and **Undo**. Undo is backed by the server operations log, so it survives a reload.
6. Say when undo will stop being available ("You can undo this for 30 days.").

### Class manager (merge, rename, delete)

Two-pane dialog. Left: searchable class list with counts. Right: the selected class with name (renames on blur or Enter, rejects duplicates inline), color swatches, usage stats (annotations, images), attribute schema, and footer actions **Merge into...** and **Delete...**.

- **Merge** shows a radio list of target classes with counts and a live preview: "1,204 annotations on 312 images will be relabeled from Van to Car. Van is removed afterward. Attribute values that Car does not define are dropped."
- **Delete** shows the danger callout, the type-to-confirm field, and a red confirm button that stays disabled until the name matches.
- Every action in the dialog leaves the dialog open on the affected class so the user can keep working.

### Class gallery

A grid of crops for every instance of a class across the project, with multi-select. Actions on the selection: change class, delete, open in image. Filters by image status, size and confidence. This is where cleanup happens.

### Empty, loading, error

Every list and panel defines all three:
- **Empty:** the empty-state pattern with one next action.
- **Loading:** skeleton rows in `--surface-2` (no spinners inside lists). The top progress bar shows longer jobs.
- **Error:** a callout with what failed, in plain words, and a retry action.

### Autosave

There is no Save button. Edits apply immediately, sync in the background, and the indicator reflects state. `Ctrl+S` shows the current sync state as a toast ("Everything is saved").

### Presence and locks

When someone else is on the same image, show their avatar (initials in a 20 px circle with a fixed color per user) in the header and a read-only banner: "Sam is editing this image. Open read-only or ask them to finish." Managers get a "Take over" action.

### Selection and multi-select

Click selects. Shift-click adds. Drag on empty canvas (select tool) draws a marquee. The Details panel shows one annotation, or a summary and bulk actions when several are selected.

## 8. Annotation canvas

| Property | Value |
|----------|-------|
| Stroke | 1.5 px; 2 px when selected. Constant on screen at any zoom (non-scaling) |
| Fill | Class color at about 8% opacity; about 22% when selected |
| Hover | Fill rises to about 15% and the label brightens |
| Label tag | Class color background, `#0B0E0C` text, 11 px / 500, radius 3, 1 x 5 px padding, above the shape's top-left corner |
| Box handles | 9 px squares, radius 2, `--bg` fill, 1.5 px class-color border, at corners. Edge handles appear when zoomed in far enough |
| Polygon vertices | Same handle style. Drag to move. Click a segment to add a vertex. Delete removes the hovered vertex |
| Draft polygon | 7 px dots. The first vertex grows to 12 px when it can close |
| Closing a polygon | Click the first vertex (within 12 screen px), press Enter, or double-click |
| Minimum shape | About 0.6% of image size on each side. Smaller drags are discarded |
| Zoom steps | 10, 25, 33, 50, 67, 75, 100, 125, 150, 200, 300, 400, 600, 800 % |
| Zoom input | `+`, `-`, `0` to fit, `Ctrl/Cmd` + wheel, pinch on touch |
| Pan | Space + drag, middle mouse, two-finger drag on touch, wheel scrolls |
| Fit | Image fits with 32 px of padding |
| Cursor | Crosshair for drawing tools, move over a selected shape, resize cursors on handles, grab while panning |
| Crosshair guide | Optional thin lines following the cursor while drawing |
| Coordinates | Bottom-left status chip: zoom, and a context hint ("Click to add points. Enter to close. Esc to cancel.") |
| Layering | Selected shape on top. Others by draw order. Locked shapes are drawn with a lock badge and ignore clicks |

Per-class controls in the classes panel: eye icon to hide, lock icon to prevent edits. Global: "Hide all" (`H`) and an opacity slider.

Model-generated annotations (`source = model`) are drawn with a dashed outline until accepted, and show their confidence in the label ("Car 0.87"). `Enter` accepts the selected one, `Delete` rejects it.

## 9. Keyboard shortcuts

All shortcuts are remappable in Settings. Tooltips read the current binding. Shortcuts are ignored while typing in an input.

| Key | Action |
|-----|--------|
| `V` | Select tool |
| `B` | Box tool |
| `P` | Polygon tool |
| `O` | Oriented box (M5) |
| `K` | Keypoints (M5) |
| `1` to `9` | Choose class. With a shape selected, also reclass it |
| `C` or `/` | Open the class search picker |
| `A` / `D` | Previous / next image |
| `Left` / `Right` | Previous / next image, or nudge the selected shape 1 px |
| `Up` / `Down` | Nudge the selected shape 1 px (`Shift` = 10 px) |
| `Tab` / `Shift+Tab` | Select next / previous annotation |
| `Delete` / `Backspace` | Delete selected |
| `Ctrl+D` | Duplicate selected |
| `Ctrl+C` / `Ctrl+V` | Copy / paste annotations (paste works across images) |
| `Shift+Enter` | Mark image done and go to the next |
| `Enter` | Close polygon, or accept a model annotation |
| `Esc` | Cancel drawing, then clear selection, then close panels |
| `Ctrl+Z` | Undo |
| `Ctrl+Shift+Z` / `Ctrl+Y` | Redo |
| `Ctrl+S` | Show sync status |
| `H` | Hide or show all annotations |
| `+` / `-` / `0` | Zoom in / out / fit |
| `Space` (hold) | Pan |
| `M` | Class manager |
| `[` | Collapse or expand the image rail |
| `N` | New project (home screen) |
| `?` | Shortcut overlay |

The class picker (`C`) is a small floating search box with the class list. It exists because the 1 to 9 keys stop being useful past nine classes.

## 10. Responsive and touch

| Width | Layout |
|-------|--------|
| 1100 px and up | Three panes as in the prototype |
| 700 to 1099 px | Rails become overlays that open over the canvas; the canvas keeps the full width |
| Under 700 px | Single pane. Toolbar at the bottom. Classes and Details open in a bottom sheet. Image list opens as a full-height drawer |

Touch density: when the primary input is coarse (`pointer: coarse`), set the density variable to "touch" and raise interactive targets to at least 40 px, with 8 px between them. Handles get an invisible 44 px hit area while staying 9 px visually.

Gestures on the canvas: one finger draws or drags with the active tool, two fingers pan and pinch zoom, a two-finger tap undoes. Drawing with a finger has an offset magnifier so the fingertip does not hide the point.

Phone use is best for review, quick boxes and tags. Do not compromise the desktop layout to make polygons comfortable on a phone.

## 11. Accessibility

Target WCAG 2.2 AA.

- **Contrast.** Body and secondary text pass 4.5:1 in both themes. The prototype's `--text-3` did not (3.1:1 on white, 2.9:1 on `--surface-1` in light, 3.6 to 4.2:1 in dark), which is why the tokens above are lighter and darker respectively. Verify any new token pair before using it. Do not use `--warning` (light) as text; use `--warning-text`. `--text-3` on `--accent-muted` is only 3.5:1 (dark) and 4.2:1 (light), so inside selected rows use `--text-2` for secondary text.
- **Form controls** need a 3:1 boundary. `--border` alone does not reach it. Inputs use `--border-strong` and keep their fill difference; check new controls.
- **Focus.** Every interactive element shows a 2 px `--accent` outline with a 2 px offset on `:focus-visible`. Never remove it. (The prototype has none, so add it.)
- **Names.** Icon-only buttons have `aria-label`. The canvas has a text alternative and a list view of annotations reachable by keyboard (`Tab` cycles annotations).
- **Not by color alone.** Status uses shape as well as color. Classes always show a name label, and pattern mode adds dash styles.
- **Live regions.** Toasts use `aria-live="polite"`. Errors use `role="alert"`.
- **Motion.** `prefers-reduced-motion` removes fades and progress easing.
- **Zoom and text size.** The interface works at 200% browser zoom without horizontal scrolling of panels.
- **RTL.** Use logical CSS properties (`margin-inline-start`, `padding-inline-end`, `inset-inline`). Mirror the layout under `dir="rtl"`. The canvas itself is never mirrored.
- **i18n.** No UI string is hardcoded in components. Use message keys, and allow 40% longer text.

## 12. Icons

One line-icon family, 16 px by default and 20 px in empty-state tiles, stroke about 1.5 to 2 px, `currentColor`. Lucide is a good fit (ISC license), and the prototype's inline icons can be replaced one for one.

Needed set: layers (projects), review, drive, search, folder, trash, plus, upload, download, select, box, polygon, tag, image, check, sun, moon, undo, redo, zoom in, zoom out, fit, chevrons, eye, eye off, lock, more (three dots), settings, users, close.

Icon-only controls always get a tooltip. Never use an icon to carry meaning that the label does not.

## 13. Writing UI text

- **Sentence case.** "Class manager", "Mark as done".
- **Verb first on buttons.** "Create project", "Import images", "Delete class". Not "OK" or "Submit".
- **Ellipsis on actions that open a dialog** ("Delete class...", "Merge into..."), and none on actions that run immediately.
- **Say what will happen, with numbers.** "1,204 annotations on 312 images will be relabeled." Use a plural helper: "1 image", "2 images".
- **Explain consequences once, plainly.** "Deleting a class removes every annotation that uses it."
- **Errors say what happened and what to do.** "A class named "car" already exists." Not "Validation error".
- **Curly quotes** around user-provided names in sentences: "Delete "Street Scenes"?"
- **No exclamation marks, no jokes, no emoji.**
- **Empty states describe what the thing is for.** "A project holds a set of images, its classes and every annotation."
- **Relative time** for recent edits ("Edited just now", "2 hours ago"), absolute dates after a week.
- **Numbers** use the user's locale separators.

## 14. Screens

**Home**
- Left sidebar: logo and version, nav (Projects with a count, Inbox), workspace switcher at the bottom (Local, or a named server with a status dot), theme toggle.
- Projects: search, "New project" (`N`), card grid, "Recent activity" panel on the right (hidden below 1100 px).
- Inbox (M3): my assigned images and my review queue across projects.

**Workspace**
- Header (48 px): logo button back to projects, breadcrumb, tool group, undo/redo, zoom controls, save indicator, Export menu, class manager, theme, presence avatars.
- Left rail: image count, filename filter, status chips, filmstrip. Collapses to 56 px with thumbnails only.
- Canvas: image, shapes, status chip at bottom-left.
- Right panel: tabs **Classes** and **Details**. Below the tabs, the image navigator (previous, next, position, filename) and the "Mark as done" button.

**Details tab.** For one selected annotation: class and type, class chips to reclassify, geometry (editable numeric fields for X, Y, W, H, or points for polygons, plus area), attributes from the class schema (toggles, option chips, text, number), and Delete.

**Dialogs.** New project (name, storage path preview, annotation types), Class manager, Delete project, Export (format, which images, split, class order), Import (source, mapping preview), Share on network (URL, QR code, HTTPS note).

**Settings.** Appearance (theme, density, pattern mode), Shortcuts, Language, Account, and for admins: Members, Server.

## 15. Changes from the prototype

Keep the layout, tokens, tone and patterns. Change these:

1. **Text contrast.** `--text-3` values changed for AA (section 2). `--warning-text` added.
2. **Focus states.** Added. The prototype has none.
3. **Fonts bundled,** including JetBrains Mono, instead of referenced.
4. **Canvas rendering.** The prototype draws shapes as DOM elements over a fixed 960 x 600 placeholder. Katib renders on Canvas 2D at the image's real size.
5. **No Save button.** Replaced with autosave and the sync indicator.
6. **Class picker.** The 1 to 9 hotkeys stay, and `C` opens a search picker for large class lists.
7. **Class hierarchy removed** from the class manager for v1 (parent class field and indented list). Attributes remain.
8. **Class gallery, health panel, presence, locks, Inbox, workspace switcher** are new.
9. **Details panel geometry** becomes editable.
10. **Arrow keys** nudge the selected shape when there is a selection, and navigate images otherwise. `A` and `D` always navigate.
11. **Responsive layout and touch density** are defined. The prototype is desktop only.
12. **Sidebar footer** ("Local workspace, ~/Katib") becomes the workspace switcher.
13. **"Undo is available until you close the project"** becomes server-backed undo with a stated retention window.
