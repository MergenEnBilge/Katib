# Working together

## Turn on accounts

By default Katib is for one person on one computer and has no sign-in. To let others use it, turn on accounts in `katib.toml`:

```toml
[auth]
mode = "local"
```

Start Katib and open it. The first person to arrive creates the administrator account. After that, everyone signs in.

If accounts are off (`mode = "none"`), Katib only listens on your own computer and refuses to start on a network address. This keeps an open instance from being exposed by accident.

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

Owners can change roles or remove people in the same window.

## How the work is shared out

- **Next image.** Annotators press **Shift+Enter** to mark an image done and are handed the next one assigned to them, or the next unassigned one.
- **Assign.** Managers can assign images to people from the review panel.
- **Soft locks.** When you open an image, Katib marks it as yours for 45 seconds and renews that while you work. Others who open it see who has it and can only look. Managers can take over a lock. Locks are advisory: if two people do edit the same shape, the second save is told the shape changed and shows the newer version.
- **Presence.** Avatars in the toolbar show who else is in the project.

## Review

Turn on **Review finished images** under Team, Settings. Images marked done then wait for a reviewer, who can approve them or send them back with a comment. Comments belong to an image and can be resolved. The **Inbox** lists what needs your attention: images assigned to you and images sent back.

## Sharing on your network

To let a phone or a colleague reach Katib on your local network:

```bash
uv run katib share
```

This turns accounts on, listens on your network, and prints an address with a QR code. Click your name at the bottom of the sidebar to see the address and code again. Everyone must be on the same network.

The address uses plain HTTP. That is fine on a network you trust, but passwords and annotations could be read by others on it, and phones cannot install Katib as an app from a plain address. For anything more, put HTTPS in front with the Docker setup in [Running a server](server.md).

## Other servers

The same window lists other Katib servers you use, saved in your browser, so you can jump between a colleague's server and your own.
