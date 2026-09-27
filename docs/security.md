# Security

This page explains what Katib protects, what it leaves to you, and what was checked.

## What Katib does

- **Passwords** are stored with argon2id. Session cookies, invite links and API tokens are stored only as hashes, so a copy of the database cannot be used to sign in.
- **Sign-in** is limited to five failed attempts per account and per visitor in five minutes.
- **Cookies** are `HttpOnly` and `SameSite=Lax`, and marked `Secure` when you use HTTPS.
- **Cross-site requests** that change data are refused when a request with a session cookie comes from another site. WebSocket connections from another site are refused too.
- **Permissions** are checked on the server for every request, not only hidden in the interface. People who are not members of a project get "not found", so they cannot even tell it exists.
- **No accounts, no network.** With `auth.mode = "none"`, Katib refuses to listen on anything but your own computer.
- **Your files.** Katib reads connected folders and never writes to them. It only reads inside folders it was allowed to use, resolves links before checking, and checks again each time it serves a picture. Only administrators can browse the server's folders on a shared server.
- **Uploads and pictures.** Files are limited in size and in pixel count (a defense against decompression bombs). Katib opens only the picture formats it supports, by their content, so a file's name cannot change how it is decoded. A single uploaded picture is stored under a generated name, never a name you typed. A folder uploaded as a folder keeps its own layout instead, because that is what lets Katib recognize a dataset inside it — every file name in it is still checked for `..` and other tricks before it touches disk, and only file types Katib actually reads (pictures and the label formats it understands) are kept.
- **Datasets you import.** XML is parsed with a library that refuses entity expansion attacks. Import paths must sit inside allowed folders.
- **Pages** are served with a strict Content-Security-Policy, `X-Frame-Options: DENY` and `nosniff`. The interface never inserts untrusted text as HTML.
- **First account.** Whoever creates the first administrator account owns the server, so Katib guards it with a setup code as soon as anybody else could get there first. A server listening on a network address asks everyone for it, including the person sitting at that computer; so does a request that arrives from a public address or through a proxy Katib was not told to trust. The code is printed when Katib starts and kept in `setup-code.txt`, and it stops working once the account exists. Guessing it is rate limited. A server that answers only on its own computer needs no code, because nobody else can reach it.
- **Settings, backups and restarts** can only be used by administrators. Passwords inside a database address are never shown again after they are saved, and the files that hold them are readable only by the account that runs Katib. Backups made in the app are deleted from the server after a day.
- **Browser features** Katib does not use, such as the camera and location, are switched off for its pages. HTTPS visits get a `Strict-Transport-Security` header.
- **No telemetry.** The one thing Katib ever fetches from the internet on its own is a model downloaded by name under Settings, and only when an administrator asks for it. Each one is pinned to a hash of the exact bytes it had when it was added to Katib's source; a download that does not match, or answers with far more data than expected, is refused rather than installed.

## What is up to you

- **Use HTTPS** for anything beyond your own computer. The Docker setup does this for you. Plain HTTP is fine on a network you trust, but passwords and pictures can be read by others on it.
- **Only set `server.behind_proxy`** when a proxy you control is the only way to reach Katib. Katib then trusts that proxy about the visitor's address. If someone can reach Katib directly, they could pretend to be anyone.
- **Keep the data folder private.** It holds the database, uploads and undo history.
- **Back up** the data folder and, with Postgres, the database. See [Running a server](server.md#backups).
- **Choose who is an administrator.** Administrators are owners of every project and can browse the server's folders.
- **Models are code.** An ONNX model runs on your server. Only use models you trust. Only administrators can add one, whether by uploading a file or downloading one of the models Katib offers.
- **Passwords you hand out.** An administrator can create an account and set its password from **Settings**, then **People**. Katib sends no email, so you pass it on yourself; do it somewhere that is not a shared channel, and let the person change it.

## What was reviewed

Before the first release the code was reviewed against the list above. That review found and fixed:

| Finding | Fix |
|---------|-----|
| WebSocket connections did not check where the page came from | Connections from another site are refused |
| Behind a proxy, every visitor looked like the proxy, so one person's failed logins could lock everyone out, and cookies were not marked `Secure` | `server.behind_proxy` makes Katib use the visitor's address and scheme from the proxy |
| Pillow decodes many formats by content, including some that call other programs | Katib opens only JPEG, PNG, WebP, BMP and TIFF |
| The model status page showed the server's folder path to every signed-in person | Only administrators see it |
| The built-in API documentation page loaded scripts from a public CDN, which the security headers blocked | The page is turned off. `/openapi.json` is still served |

A second review covered the settings page, backups, restore, the setup code, the practice project and the Android app. It found and fixed:

| Finding | Fix |
|---------|-----|
| A proxy in front of Katib that was not marked as trusted made every visitor look like a private address, which would have skipped the setup code | Requests that carry proxy headers need the code unless `server.behind_proxy` is on |
| Files holding a database password or the setup code used the default file permissions | They are readable only by the owner where the system supports it |
| Backup zips, which contain every password hash, stayed on the server | They are deleted after 24 hours |
| Pages could ask the browser for the camera, microphone or location | A Permissions-Policy header switches them off |

A third review, before 0.1.0, went through every route in the API, the file handling, the new
click-to-select and account pages, and the phone app. It found and fixed:

| Finding | Fix |
|---------|-----|
| Whoever reached a server on a shared network first could claim the administrator account without the setup code, because Katib treated a private address as proof of trust. An office or cafe wifi is not a list of people you trust | Any server open to a network asks everyone for the code |
| The progress and result of a backup, including the name of the file it wrote, could be read by any signed-in person, though the file itself could not be downloaded | Jobs that belong to no project are administrators' only |
| Making a QR code needed administrator rights, so a project manager could create a phone invite but not show it | Anyone signed in can render a code; the server's own addresses are still administrators' only |

Dependencies are checked with `pnpm audit`, `npm audit` and `pip-audit`. Nothing that ships has a
known vulnerability. The tools that build the Android icons do: `@capacitor/assets` pulls in old
copies of `tar`, `sharp` and `uuid`, with no fixed version published. They run on a build machine
and no part of them is inside the app, so the audit of what ships is clean while the full
development audit is not.

Uploading a whole folder, added after 0.1.0, was reviewed on its own since it is the one upload
path where a name you typed reaches the filesystem rather than a name Katib generated. Every file
name in the folder is split into segments and checked for `..`, an empty segment, and a bare
Windows drive letter before anything is written, and the storage layer underneath checks again,
independently, that the result still sits inside its own folder. Only file types Katib already
reads — pictures, and the label files the format readers understand — are kept; anything else in
the folder is left out rather than written to disk unread.

## Known limits

- The database connection test in Settings connects to whatever address an administrator types, like any tool that can talk to a database. Only administrators can use it.
- The Android app allows plain HTTP addresses, because home servers usually have no certificate. It warns before connecting to one that is not on a private network.
- Compressed API replies are a known trade-off on encrypted connections. Katib's replies do not mix secret values with text an attacker can choose, which is what such attacks need.

- Click to select runs a model for whoever clicks. A member of a project could use it to keep a
  server's processor busy. It is not open to strangers, and the first click on a picture is the
  only expensive one, but there is no quota on it.
- Login attempts are counted in memory, so a restart resets them, and separate server processes do not share them.
- Locks and presence are advisory. They prevent almost all edit conflicts, and version checks catch the rest.
- There is no built-in single sign-on, two-factor sign-in, or audit log beyond project activity and the history of bulk changes.

## Reporting a problem

If you find a security problem, please do not open a public issue. Use [GitHub's private vulnerability reporting](https://github.com/MergenEnBilge/Katib/security/advisories/new) on the repository. Include what you did and what you saw. You will get an answer, and a fix is credited to you if you like.
