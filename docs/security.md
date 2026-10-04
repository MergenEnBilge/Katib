# Security

This page explains how Katib protects your data, what you need to take care of yourself, and how to
report a problem.

## What Katib protects

**Passwords.** Passwords are stored with argon2id, a scheme designed to slow down guessing. Session
cookies, invite links and API tokens are stored only as hashes. Someone who copies the database
cannot sign in with what they find.

**Sign-in attempts.** After five failed attempts in five minutes, Katib blocks further attempts for that
account and that visitor's address.

**Cookies.** Session cookies cannot be read by page scripts. They are sent only to Katib, and they are
marked `Secure` when you use HTTPS.

**Requests from other websites.** A page on another website cannot change your data through your browser.
Katib refuses any request that comes from another site, whether or not you are signed in. WebSocket
connections are checked the same way.

**Name tricks.** Some attacks point a domain name at your own computer, so that a website can talk to
your local Katib. While Katib only listens on your computer, it accepts requests addressed to
`localhost`, `127.0.0.1` and `::1`, and nothing else.

**Permissions.** The server checks permissions on every request. Hiding a button is never the only
protection. People who are not members of a project get "not found" when they try to open it, so they
cannot tell that it exists.

**Accounts and the network.** With accounts off, Katib refuses to listen on anything except your own
computer. You cannot share an open copy by accident.

**Your pictures.** Katib reads connected folders but never writes to them. It only reads from folders you
allowed, and it checks that again each time it shows a picture. Links are resolved before the check, so a
link cannot lead out of an allowed folder. On a shared server, only administrators can browse the
server's folders.

**Uploads.** Uploaded files have size limits, and pictures have a pixel limit. This stops a tiny file from
expanding into something huge when it is opened. Katib opens only the picture types it supports, and it
checks each file's contents, not its name. An uploaded picture is stored under a name Katib creates, never
a name you typed.

**Folder uploads.** A folder keeps its layout, because that is how Katib recognises a dataset inside it.
Every file name is checked for `..` and other tricks before anything is written. Only pictures and label
files that Katib reads are kept. Anything else in the folder is skipped.

**Imported datasets.** Katib reads XML with a parser that refuses entity expansion attacks. Import paths
must be inside an allowed folder.

**Pages.** Pages are served with a strict Content-Security-Policy, which limits what scripts can do. Katib
does not embed other pages, and it does not turn untrusted text into HTML. The browser is also told not to
guess file types, and to switch off the camera, microphone and location.

**The first account.** Whoever creates the first administrator account controls the server. Katib therefore
asks for a **setup code** before it creates that account whenever another person could reach the server
first. The code is printed when Katib starts and saved in `setup-code.txt`. It stops working once the
account exists. Guessing it is rate limited.

A server that only answers on its own computer does not ask, because nobody else can reach it.

**Cloud keys.** A bucket's key is kept in `cloud-sources.json` in the data folder, which only the
account running Katib can read, and it is never sent back to a browser. The list of buckets shows
what is set up, not how to open it. Katib signs its own requests and only ever reads, so a key that
can only read is enough and is what to give it. A backup includes this file, because a restored
server would otherwise be unable to open those pictures; keep backups somewhere private.

**Settings, backups and restarts.** Only administrators can change settings, make backups, or restart
Katib. A password inside a database address is never shown again after you save it. Backup files are
deleted from the server after a day, because they contain password hashes.

**Models.** The model downloads Katib offers are checked against a fixed hash, so a download that does
not match is refused.

**No telemetry.** Katib does not report usage anywhere. The only thing it downloads on its own is a model
that an administrator asks for by name.

**Teams.** Owners and administrators can add, change and remove anyone on a project. Managers can add,
change and remove annotators, reviewers and viewers. They cannot give out, change or remove ownership or
management. A project always keeps at least one owner.

Searching for people is limited to administrators. Owners and managers who are not administrators must type
the whole email address. This means owning a project does not let you list every account on the server.

An invite stops working when the person who sent it can no longer add people.

**Stopping the server.** A program on the same computer can ask the server to stop. The request has to
come directly from that computer, not through a proxy. It also has to include a token that the server
writes to `server.json` in its data folder. Only the account that runs Katib can read that file.

Only one server runs for each data folder. The lock is released by the operating system when the server
ends, even if it crashes, so a stopped server never leaves a folder looking busy.

## What you need to take care of

**Use HTTPS** for anything beyond your own computer. The Docker setup handles this. Plain `http` is fine on
a network you trust, but other people on that network can read passwords and pictures.

**Set `server.behind_proxy` only when the proxy is the only way in.** Katib then believes the proxy about
each visitor's address and about HTTPS. If people can reach Katib without going through the proxy, they can
pretend to be anyone.

**Keep the data folder private.** It holds the database, uploads and undo history.

**Back up regularly**, and keep the backup somewhere other than the server. See
[Running a server](server.md#backups).

**Choose your administrators carefully.** Administrators own every project, can read every account's name and
email, and can browse the server's folders.

**Treat models as code.** An ONNX model runs on your server. Use only models you trust. Only administrators
can add one, by uploading a file or downloading one of the models Katib offers.

**Pass on passwords carefully.** Katib does not send email. Give new passwords in person, or through a private
channel, and ask the person to change them straight away.

## Known limits

- The database connection test in Settings connects to whatever address an administrator types. Only
  administrators can use it.
- The Android app allows plain `http` addresses, because home servers often have no certificate. It warns
  you before connecting to an address that is not on a private network.
- Click to select runs a model on the server for anyone who uses it. Each picture's first click is the slow
  one. There is no usage limit, so a project member could keep the server busy.
- Sign-in attempts are counted in memory. A restart clears the count.
- Locks and presence are advisory. They prevent most edit conflicts, and a version check catches the rest.
- Katib has no single sign-on, two-factor sign-in, or full audit log. It keeps a history of project activity
  and bulk changes.

## Reporting a problem

Please do not report security problems in a public issue. Use
[GitHub's private vulnerability reporting](https://github.com/MergenEnBilge/Katib/security/advisories/new).
Describe what you did and what happened. Fixes are listed in the [changelog](https://github.com/MergenEnBilge/Katib/blob/main/CHANGELOG.md), and you are
credited if you want to be.
