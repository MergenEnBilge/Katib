/**
 * The English text. Every other language is a copy of this file with the same keys.
 *
 * Keys are grouped by screen. A `{name}` in a message is filled in by the caller. Messages that
 * depend on a number come in two forms, `key.one` and `key.other`, and `tp()` picks the right
 * one for the language.
 */
const en = {
  'nav.projects': 'Projects',
  'nav.inbox': 'Inbox',
  'nav.settings': 'Settings',
  'nav.help': 'Help',
  'nav.main': 'Main',
  'nav.signOut': 'Sign out',
  'nav.localWorkspace': 'Local workspace',
  'nav.workspaceHint': 'Share this computer or switch to another server',
  'nav.signedIn': 'Signed in',
  'theme.toLight': 'Switch to light theme',
  'theme.toDark': 'Switch to dark theme',
  'time.never': 'never',
  'time.justNow': 'just now',
  'loading': 'Loading',
  'tryAgain': 'Try again',
  'notFound.title': 'Page not found',
  'notFound.body': 'This address does not match anything in Katib.',
  'notFound.back': 'Back to projects',

  'projects.title': 'Projects',
  'projects.search': 'Search projects',
  'projects.new': 'New project',
  'projects.empty.title': 'No projects yet',
  'projects.empty.body': 'A project holds a set of images, its classes and every annotation.',
  'projects.noMatch': 'No project matches “{query}”.',
  'projects.images.one': '{count} image',
  'projects.images.other': '{count} images',
  'projects.done': '{done} of {total} done',
  'projects.doneLabel': 'Images done',
  'projects.edited': 'Edited {when}',
  'projects.loadFailed': 'Could not load projects.',

  'auth.setup.title': 'Set up Katib',
  'auth.setup.lead': 'Create the administrator account. This screen only appears while no account exists.',
  'auth.setup.submit': 'Create administrator',
  'auth.setup.code': 'Setup code',
  'auth.setup.codeHint': 'This server can be reached from the internet. Find the code in the server log, or in setup-code.txt in its data folder.',
  'auth.invite.title': 'Create your account',
  'auth.invite.submit': 'Create account',
  'auth.signin.title': 'Sign in',
  'auth.signin.lead': 'Use the account you were given.',
  'auth.signin.submit': 'Sign in',
  'auth.email': 'Email',
  'auth.name': 'Your name',
  'auth.password': 'Password',
  'auth.passwordHint': 'At least 10 characters.',
  'auth.failed': 'Something went wrong. Try again.',
} as const;

export type MessageKey = keyof typeof en;
export type Messages = Record<MessageKey, string>;

export default en as Messages;
