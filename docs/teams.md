# Working together

## Turn on accounts

By default Katib is for one person on one computer and has no sign-in. Open **Settings**, then
**Sharing**, and pick how you want to use it:

| | What it does |
|---|---|
| **Just me** | Katib answers on this computer only. No sign-in |
| **My team, on this network** | Everyone on the same wifi signs in and shares projects. Phones can join |
| **Over the internet** | The same, for a server behind a proxy that handles HTTPS |

Each one sets several settings together — who signs in, which addresses Katib answers on, and
whether to trust a proxy. The individual settings stay underneath if you want to arrange them
yourself.

Choosing anything but **Just me** needs a restart, and Katib offers you the button. The first person
to open it afterwards creates the administrator account; after that, everyone signs in.

With accounts off, Katib only listens on your own computer and refuses to start on a network
address. That keeps an open instance from being exposed by accident.

## Roles

| Role | What they can do |
|------|------------------|
| Owner | Everything, including deleting the project and managing members |
| Manager | Import, manage classes, assign images, review, export |
| Reviewer | Annotate, approve or send back finished images, comment |
| Annotator | Annotate and mark images done |
| Viewer | Look, but not change anything |

Administrators are owners of every project. People who are not members of a project cannot see that it exists.

## Inviting people

Open a project, choose **Team**, pick a role and create an invite link. Send it only to the person you are inviting. A link works once and expires after seven days. The person opens it, chooses a password, and joins the project with that role.

The link carries an address other people can open, not whatever is in your own address bar. If you reached Katib at `localhost`, the invite still points at the address your colleagues use.

Owners can change roles or remove people in the same window.

## How the work is shared out

- **Next image.** Annotators press **Shift+Enter** to mark an image done and are handed the next one assigned to them, or the next unassigned one.
- **Assign.** Managers can assign images to people from the review panel.
- **Soft locks.** When you open an image, Katib marks it as yours for 45 seconds and renews that while you work. Others who open it see who has it and can only look. Managers can take over a lock. Locks are advisory: if two people do edit the same shape, the second save is told the shape changed and shows the newer version.
- **Presence.** Avatars in the toolbar show who else is in the project.

## Review

Turn on **Review finished images** under Team, Settings. Images marked done then wait for a reviewer, who can approve them or send them back with a comment. Comments belong to an image and can be resolved. The **Inbox** lists what needs your attention: images assigned to you and images sent back.

## Sharing on your network

Pick **My team, on this network** in Settings, or start Katib with:

```bash
uv run katib share
```

which turns accounts on, listens on your network, and prints an address with a QR code.

Click your name at the bottom of the sidebar at any time for the address, a code to point a phone
camera at, and a second code that downloads the Android app. Everyone must be on the same network.

Katib works the address out from the one your browser used to reach it, so it is the address that
demonstrably gets through rather than a guess. Two things change that:

- **Running in Docker**, Katib cannot see the address of the machine hosting it, and says so instead
  of showing one that leads nowhere. Open Katib once from the device you want to share with, using
  that machine's address, and it will know from then on.
- **Behind a proxy or on a real domain**, set the public address under **Settings**, then
  **Sharing**. That address then wins everywhere, including invite links.

The address uses plain HTTP. That is fine on a network you trust, but passwords and annotations could be read by others on it, and phones cannot install Katib as an app from a plain address. For anything more, put HTTPS in front with the Docker setup in [Running a server](server.md).

## Other servers

The same window lists other Katib servers you use, saved in your browser, so you can jump between a colleague's server and your own.
