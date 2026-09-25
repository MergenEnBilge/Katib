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
- **Uploads and pictures.** Files are limited in size and in pixel count (a defense against decompression bombs). Katib opens only the picture formats it supports, by their content, so a file's name cannot change how it is decoded. Uploaded files are stored under generated names, never a name you typed.
- **Datasets you import.** XML is parsed with a library that refuses entity expansion attacks. Import paths must sit inside allowed folders.
- **Pages** are served with a strict Content-Security-Policy, `X-Frame-Options: DENY` and `nosniff`. The interface never inserts untrusted text as HTML.
- **No telemetry.** Katib makes no network requests on its own.

## What is up to you

- **Use HTTPS** for anything beyond your own computer. The Docker setup does this for you. Plain HTTP is fine on a network you trust, but passwords and pictures can be read by others on it.
- **Only set `server.behind_proxy`** when a proxy you control is the only way to reach Katib. Katib then trusts that proxy about the visitor's address. If someone can reach Katib directly, they could pretend to be anyone.
- **Keep the data folder private.** It holds the database, uploads and undo history.
- **Back up** the data folder and, with Postgres, the database. See [Running a server](server.md#backups).
- **Choose who is an administrator.** Administrators are owners of every project and can browse the server's folders.
- **Models are code.** An ONNX model runs on your server. Only use models you trust.

## What was reviewed

Before the first release the code was reviewed against the list above. That review found and fixed:

| Finding | Fix |
|---------|-----|
| WebSocket connections did not check where the page came from | Connections from another site are refused |
| Behind a proxy, every visitor looked like the proxy, so one person's failed logins could lock everyone out, and cookies were not marked `Secure` | `server.behind_proxy` makes Katib use the visitor's address and scheme from the proxy |
| Pillow decodes many formats by content, including some that call other programs | Katib opens only JPEG, PNG, WebP, BMP and TIFF |
| The model status page showed the server's folder path to every signed-in person | Only administrators see it |
| The built-in API documentation page loaded scripts from a public CDN, which the security headers blocked | The page is turned off. `/openapi.json` is still served |

Dependencies are checked with `pnpm audit` and `pip-audit`, and neither reports known vulnerabilities in what ships.

## Known limits

- Login attempts are counted in memory, so a restart resets them, and separate server processes do not share them.
- Locks and presence are advisory. They prevent almost all edit conflicts, and version checks catch the rest.
- There is no built-in single sign-on, two-factor sign-in, or audit log beyond project activity and the history of bulk changes.

## Reporting a problem

If you find a security problem, please do not open a public issue. Use [GitHub's private vulnerability reporting](https://github.com/MergenEnBilge/Katib/security/advisories/new) on the repository. Include what you did and what you saw. You will get an answer, and a fix is credited to you if you like.
