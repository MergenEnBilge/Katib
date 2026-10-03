# Working together

This guide covers turning on accounts, the roles people can have, how to invite people, and how work is
shared between them.

## Turn on accounts

By default, Katib is for one person on one computer, and it does not ask you to sign in. To work with a
team, open **Settings**, then **Sharing**, and choose one of these:

| Choice | What it means |
|--------|---------------|
| **Just me** | Katib only answers on this computer. There is no sign-in. |
| **My team, on this network** | Everyone on the same Wi-Fi signs in and shares projects. Phones can join too. |
| **Over the internet** | The same as above, for a server behind a proxy that handles HTTPS. |

Each choice sets several settings together: who has to sign in, which addresses Katib listens on, and
whether it trusts a proxy. You can still change the individual settings yourself.

Katib needs a restart after you choose anything except **Just me**. It offers you a button for that.

### The setup code

After the restart, the first person to open Katib creates the administrator account. That account runs
the server, so Katib asks for a setup code first. The code is printed in the server log when Katib
starts, and saved in `setup-code.txt` in the data folder. Once the account exists, the code stops
working.

The code matters. Anyone who can reach Katib could otherwise create the account before you do. The Wi-Fi
at an office or a café is not a list of people you trust.

With accounts turned off, Katib only listens on your own computer, and it refuses to start on a network
address. This stops an open copy from being reachable by accident.

## Roles

| Role | What they can do |
|------|------------------|
| **Owner** | Everything, including deleting the project and managing the team |
| **Manager** | Import pictures, manage classes, assign pictures, review and export. Can add, change and remove annotators, reviewers and viewers |
| **Reviewer** | Label pictures, approve finished pictures or send them back, and leave comments |
| **Annotator** | Label pictures and mark them as done |
| **Viewer** | Look at the project, without changing anything |

Administrators are owners of every project. Someone who is not a member of a project cannot see that it
exists.

## Inviting people

Open a project and choose **Team**. Pick a role and create an invite link. Send the link only to the
person you are inviting. A link works once and expires after seven days. The person opens it, chooses a
password, and joins the project in the role you picked.

You can also open the same window from the project list. Each project card has a **Manage team** option
in its menu, so you do not need to open the project first.

Next to the role, choose whether the person will work **on a computer** or **on a phone**. For a phone,
Katib shows a code to scan with the camera instead of a link. The code opens the invite in the Katib app,
or offers to download the app first. Either way, the person joins the same project.

The link uses an address that other people can open. If Katib does not know that address, it tells you
so, and does not make a link to `localhost`. Click your name at the bottom of the sidebar and enter the
address.

Owners can change roles and remove people in the same window. Managers can do this for annotators,
reviewers and viewers.

### Deleting a project

Only owners can delete a project. You can do this from the **Settings** tab in the Team window, or from
the project's card in the list. Katib asks you to type the project name to confirm. Deleting cannot be
undone. The pictures you uploaded are deleted too. Pictures in a folder you connected are not, because
Katib never copied them.

## Adding accounts yourself

Invites suit people who will sign up on their own. If you would rather create the accounts yourself,
open **Settings**, then **People**. You can:

- add someone with an email address, a name and a password
- make someone an administrator
- set a new password for someone who has forgotten theirs
- sign someone out and turn their account off when they leave

Katib does not send email, so give people their password yourself. Changing a password signs that
person out on every device. This is useful if you changed it because something went wrong.

Turning off an account keeps the person's name on the work they did. Katib does not delete people,
because their labels would lose their author.

A new account can sign in, but it is not part of any project yet. Add it from a project's **Team**
window. If you make it an administrator, it becomes an owner of every project.

## How the work is shared

- **Next picture.** Annotators press **Shift+Enter** to mark a picture as done. Katib then opens the next
  picture assigned to them, or the next unassigned one.
- **Assigning.** Managers can assign pictures to people from the review panel.
- **Locks.** When you open a picture, Katib reserves it for you for 45 seconds, and keeps extending that
  while you work. Anyone else who opens it can see who has it and can only look. Managers can take over a
  lock. If two people change the same shape, the second save is refused, and Katib shows the newer
  version.
- **Who is here.** Small avatars in the toolbar show who else is in the project right now.

## Review

Turn on **Review finished pictures** under **Team**, then **Settings**. Pictures marked as done then wait
for a reviewer. The reviewer can approve them, or send them back with a comment. Comments belong to one
picture, and you can mark them as resolved. The **Inbox** lists the pictures that need your attention:
ones assigned to you and ones sent back.

## Sharing on your network

Choose **My team, on this network** in **Settings**. Or start Katib from a terminal with:

```bash
uv run katib share
```

This turns on accounts, makes Katib listen on your network, and prints an address and a QR code. Everyone
must be on the same network.

Click your name at the bottom of the sidebar at any time to see the address. The same panel shows a code
for a phone camera, and a second code that downloads the Android app.

Katib works out the address from the one your browser used to reach it. Two cases need your help:

- **In Docker**, the address inside the container is not the one other computers can reach. Katib asks
  for it. Type the address of the computer that runs Docker. On Windows, run `ipconfig` to find it. On a
  Mac or Linux computer, run `hostname -I`. Katib remembers the address and uses it for every code and
  invite link.
- **Behind a proxy or on a domain name**, enter that address in the same box, or set the public address
  under **Settings**, then **Sharing**. It takes priority everywhere, including invite links.

If the address changes later, choose **Not the right address?** under the code, and enter the new one.

The address uses plain HTTP. That is fine on a network you trust. On any other network, other people
could read passwords and labels, and phones will not install the app from a plain address. For anything
more, put HTTPS in front of Katib. [Running a server](server.md) explains how.

## Other servers

The window keeps a list of the Katib servers you use. It is saved in your browser, so you can switch
between a colleague's server and your own.
