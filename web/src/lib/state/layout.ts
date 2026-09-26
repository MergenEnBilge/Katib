/**
 * Which panels someone has folded away, remembered between visits.
 *
 * Folding a panel is a choice about how you like to work, so it should still be that way tomorrow.
 */

export interface Layout {
  /** The navigation column on the home screen. */
  sidebar: boolean;
  /** The list of images down the side of the workspace. */
  rail: boolean;
  /** The classes and details column in the workspace. */
  panel: boolean;
  /** Which tab of that column was open. */
  tab: string;
}

export const LAYOUT_KEY = 'katib.layout';

export const OPEN: Layout = { sidebar: false, rail: false, panel: false, tab: 'classes' };

const TABS = ['classes', 'details', 'review', 'text'];

/** Read a remembered layout. Anything unexpected falls back to everything open. */
export function parseLayout(raw: string | null): Layout {
  if (!raw) return OPEN;
  try {
    const data = JSON.parse(raw) as Record<string, unknown>;
    return {
      sidebar: data.sidebar === true,
      rail: data.rail === true,
      panel: data.panel === true,
      tab: typeof data.tab === 'string' && TABS.includes(data.tab) ? data.tab : OPEN.tab,
    };
  } catch {
    return OPEN;
  }
}
