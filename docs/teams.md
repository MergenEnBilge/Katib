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

Open a project, choose **Team**, pick a role and create an invite link. Send it only to the person
you are inviting. A link works once and expires after seven days. The person opens it, chooses a
password, and joins the project with that role.

Next to the role there is a second choice: whether they will be working **on a computer** or **on a
phone**. Pick a phone and you get a code to hold a camera up to instead of a link to send. When
they scan it, Android offers to open the invite in the Katib app, and offers to download the app
first if they do not have it. Either way they land on the same page and join the same project.

The link carries an address other people can open, not whatever is in your own address bar. If
Katib does not know that address it says so instead of sending out a link to `localhost`; click
your name at the bottom of the sidebar and tell it.

Owners can change roles or remove people in the same window.

## Handing out accounts instead

Invites suit people who will sign themselves up. When you would rather create the accounts
yourself, open **Settings**, then **People**. You can add someone with an email address, a name and
a password, make them an administrator, give someone a new password when they forget theirs, and
shut someone out when they leave.

Katib sends no email, so tell people their password yourself. Changing a password signs that person
out everywhere at once, which is what you want if you are changing it because something went wrong.

Shutting someone out keeps their name on the work they did. There is no way to delete a person,
because their annotations would lose their author.

An account created here can open Katib but is not in any project yet. Add them from the project's
**Team** window, or make them an administrator, which makes them an owner of everything.

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

- **Running in Docker**, Katib cannot see the address of the machine hosting it: from inside the
  container the only address in sight is the container's own, which nothing outside Docker can
  reach. So it asks. Type the address of the computer Docker is running on — `ipconfig` on Windows,
  `hostname -I` on a Mac or Linux — and Katib remembers it and builds every code and invite link
  from it.
- **Behind a proxy or on a real domain**, put that address in the same box, or set the public
  address under **Settings**, then **Sharing**. It wins everywhere, including invite links.

If the address ever changes, **Not the right address?** under the code lets you replace it.

The address uses plain HTTP. That is fine on a network you trust, but passwords and annotations could be read by others on it, and phones cannot install Katib as an app from a plain address. For anything more, put HTTPS in front with the Docker setup in [Running a server](server.md).

## Other servers

The same window lists other Katib servers you use, saved in your browser, so you can jump between a colleague's server and your own.
