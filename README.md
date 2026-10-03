<p align="center">
  <img src="brand/logo.svg" width="96" height="96" alt="Katib">
</p>

<h1 align="center">Katib</h1>

<p align="center"><strong>Label images with your team, on your own computer.</strong></p>

<p align="center">
  <a href="https://github.com/MergenEnBilge/Katib/actions/workflows/ci.yml"><img src="https://github.com/MergenEnBilge/Katib/actions/workflows/ci.yml/badge.svg" alt="Build status"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-1f7a4c" alt="MIT licensed"></a>
  <img src="https://img.shields.io/badge/python-3.12%2B-1f7a4c" alt="Python 3.12 or newer">
</p>

<p align="center">
  <img src="docs/images/workspace.png" width="900" alt="The Katib workspace: an image with labelled boxes, the picture list on the left, classes on the right">
</p>

Katib is an annotation tool for computer vision. You draw boxes and shapes on your pictures, sort
them into classes, and export them in the format your training code already reads.

It runs on your own computer, so your pictures stay where they are. Start it on a laptop with one
command, or run it on a server that your whole team signs in to.

Built by M. Abdullah K. Mughal ([MergenEnBilge](https://github.com/MergenEnBilge)).

## Why people use it

- **It is quick to use from the keyboard.** Number keys pick a class, the arrow keys move a shape
  one pixel at a time, and `Shift+Enter` marks a picture as done and opens the next one.
- **Changes save as you make them.** There is no save button to forget.
- **Mistakes are easy to fix.** Rename a class and every shape follows it. Merging or deleting a
  class shows you what it will change first, and History keeps 30 days of undo.
- **It checks your data before you train.** It finds tiny shapes, duplicate boxes, near-identical
  photos that could leak between your training and validation sets, and classes with very few
  examples.
- **It works with the formats you already have.** Import and export YOLO, COCO, Pascal VOC,
  LabelMe and JSON Lines. Train, validation and test splits are kept.
- **It does not phone home.** There is no account to create with us, no telemetry and no licence
  check. The only download Katib makes on its own is a model you ask for by name.

## Install

| What you want | What to do |
|---------------|------------|
| Katib on your computer | Download the installer for [Windows, macOS or Linux](https://github.com/MergenEnBilge/Katib/releases) and open it |
| Katib for your team | Run the Docker command below |
| Katib on Android | Install `Katib-android.apk` from the [releases page](https://github.com/MergenEnBilge/Katib/releases) |
| Katib on an iPhone or iPad | Open your Katib address in Safari, then choose **Add to Home Screen** |
| Katib from the source code | See [Getting started](docs/getting-started.md#from-the-source) |

To run Katib with Docker, paste this into a terminal:

```bash
docker run -d --name katib --restart unless-stopped -p 8420:8420 -v katib-data:/data ghcr.io/mergenenbilge/katib:v0.5.1
```

Then open <http://localhost:8420>. The first time, Katib asks for a setup code. Run
`docker exec katib cat /data/setup-code.txt` to see it. The
[install guide](docs/getting-started.md) covers each platform, including the warning Windows and
macOS show for software that is not code-signed yet.

New to Katib? On the home page, choose **Try it with practice pictures**. You get a small project
and a short tour.

<p align="center">
  <img src="docs/images/projects.png" width="900" alt="The Katib home screen with a welcome checklist and a project card">
</p>

## What you can label

- **Boxes**, for most objects.
- **Polygons**, for shapes with an outline.
- **Rotated boxes**, for things at an angle.
- **Keypoints**, with skeletons, for poses.
- **Brush masks**, for painting over an area.
- **Whole-image tags**, and **text** for captions or transcriptions.

Each project uses only the kinds you pick when you create it, so the toolbar stays simple.

Two tools can draw for you. The **magic wand** outlines an object that stands out from its
background, and needs no model. With a Segment Anything model, **click to select** outlines things
the wand cannot follow, and a shift-click adds what it missed. Both run on your own computer.

<p align="center">
  <img src="docs/images/health.png" width="820" alt="The dataset health window listing images without shapes, tiny shapes, duplicates and class balance">
</p>

Before you start a training run, the health panel points out problems that are easy to miss.

Katib also reads the train, validation and test folders in a dataset you bring in. It keeps each
picture in its split and uses the same split when you export. You can shuffle the splits with a seed
you choose, or set the ratios for each project.

<p align="center">
  <img src="docs/images/splits.png" width="820" alt="The split window with train, validation and test shares and a preview of what will move">
</p>

## Working with a team

Invite people with a link, and give each one a role: owner, manager, annotator, reviewer or viewer.
Someone working on a phone can scan a code instead of typing a link. You can also create accounts
yourself in Settings.

Katib gives each annotator the next picture, shows who else is on the project, and stops two people
from editing the same picture at once. Reviewers can approve a picture or send it back with a
comment.

<p align="center">
  <img src="docs/images/settings.png" width="900" alt="Katib settings, showing who can use it, how it is reached, and the port">
</p>

Settings are written in plain language, and each one says whether it takes effect straight away or
after a restart. Sharing starts with three choices: just you, your team on this network, or the
internet. Backups are one click.

## On a phone or tablet

Katib works in a phone browser, and the Android app connects to the same server. Click your
workspace name on a computer to show two codes. One downloads the Android app. The other connects
the app to your server by scanning it, so nobody has to type an address on a phone.

If you add Katib to your home screen, it keeps working when the signal drops. Anything you draw
while offline is sent when you are connected again.

<p align="center">
  <img src="docs/images/phone.png" width="300" alt="Katib on a phone, showing a picture with labelled boxes">
</p>

## Using it with other tools

| If you want to | Do this |
|----------------|---------|
| Train a model | Export YOLO, COCO, VOC, LabelMe or JSON Lines, with or without the pictures |
| Script your work | Use the [REST API](docs/automation.md) or the [Python client](sdk/README.md) |
| Use your own model | Load an ONNX detector to draft boxes, or a Segment Anything model to outline objects |
| Use a phone or tablet | Install the Android app, or add Katib to your home screen |
| Share on your network | Run `katib share` to get an address and a QR code |

## Documentation

| Guide | What it covers |
|-------|----------------|
| [Getting started](docs/getting-started.md) | Installing Katib and making your first project |
| [Drawing and shortcuts](docs/drawing.md) | Each tool and every key |
| [Pictures, folders and formats](docs/data.md) | Importing datasets, connecting folders, exporting |
| [Classes and dataset health](docs/classes.md) | Renaming and merging classes, and the health checks |
| [Working together](docs/teams.md) | Accounts, invites, roles and review |
| [Putting Katib online](docs/deploy.md) | Docker, HTTPS, Postgres and Raspberry Pi |
| [Running a server](docs/server.md) | Settings, backups and upgrades |
| [Automation](docs/automation.md) | The REST API and the Python client |
| [How Katib is built](docs/internals.md) | The structure of the code |
| [Security](docs/security.md) | What Katib protects, and what you need to take care of |

To read the guides as a website, run `uv run --group docs mkdocs serve`.

## Changes

See the [changelog](CHANGELOG.md) for what changed in each release.

## Contributing

Katib's back end is Python with FastAPI and SQLAlchemy. The front end is Svelte and TypeScript, and
the drawing canvas is a small engine written without a framework. The [internals guide](docs/internals.md)
explains how the parts fit together, and [contributing](docs/contributing.md) covers setup and the
checks.

```bash
uv sync --all-extras
pnpm --dir web install
uv run katib dev              # back end on port 8420, reloads on change
pnpm --dir web dev            # front end on port 5173, sends /api to the back end
```

Found a security problem? Please report it privately through
[GitHub security advisories](https://github.com/MergenEnBilge/Katib/security/advisories/new)
rather than in a public issue.

## Limits

- The installers are not code-signed yet, so Windows and macOS warn you the first time you open one.
- The Android app is signed with a debug key unless you set up a release key.
- The interface is in English for now.

## Licence

Katib is released under the MIT licence. See [LICENSE](LICENSE). The tray icon uses pystray, which
is LGPL-3.0 licensed, and ships as a separate file so it can be replaced.
