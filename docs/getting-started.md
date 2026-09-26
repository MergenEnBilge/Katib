# Install and first project

## Pick a way to install

| You want | Use | Takes |
|----------|-----|-------|
| Katib on my own computer | The installer for [Windows](#windows), [macOS](#macos) or [Linux](#linux) | 2 minutes |
| Katib for my team, on a server | [Docker](#a-server-for-your-team) | 5 minutes |
| Katib on my Android phone | [The app](#android) | 2 minutes |
| Katib on my iPhone or iPad | [Add it to the home screen](#iphone-and-ipad) | 1 minute |
| To change Katib itself | [From the source](#from-the-source) | 5 minutes |

Whichever you choose, your images and labels stay on your own hardware. Katib makes no network
requests of its own.

!!! note "Katib is still on release candidates"

    The downloads are marked pre-release, which is honest rather than ominous: the checks run on
    every change, but the version number has not settled. Replace `<version>` below with the one on
    the [releases page](https://github.com/MergenEnBilge/Katib/releases), currently `0.1.0-rc2`.

!!! warning "Copying commands on Windows"

    Every command here is one line. Copy the whole line. Guides often break long commands across
    several lines with a `\` at the end, which a Mac or Linux terminal understands and PowerShell
    does not — it reads them as separate commands and fails with `invalid reference format`.

## Windows

1. Download `Katib-<version>-windows-setup.exe` from the
   [releases page](https://github.com/MergenEnBilge/Katib/releases).
2. Open it. It installs for you alone and needs no administrator password.
3. Windows may say it does not recognise the publisher, because the file is not code-signed yet.
   Choose **More info**, then **Run anyway**.
4. Start Katib from the Start menu or the desktop shortcut.

Katib opens in its own window. It runs a server on your computer only, on a port nothing else can
reach, and closing the window stops it.

Prefer no installer? The archive of `dist\Katib` from a build works as a portable folder: run
`Katib.exe` inside it.

## macOS

1. Download `Katib-<version>-macos.dmg` from the releases page.
2. Open it and drag **Katib** into **Applications**.
3. The first time, right-click the app and choose **Open**, then confirm. macOS blocks a normal
   double-click because the app is not signed with an Apple developer certificate yet. You only do
   this once.

## Linux

The package is built on Ubuntu 22.04, so it runs on **Ubuntu 22.04, Debian 12, Raspberry Pi OS
bookworm or newer**. On something older, use Docker instead.

=== "Debian, Ubuntu, Raspberry Pi OS"

    ```bash
    sudo apt install ./katib_<version>_amd64.deb
    ```

    `apt` pulls in the two libraries Katib needs, GTK and WebKitGTK. Then start **Katib** from your
    applications menu, or run `katib-app`.

=== "Any other distribution"

    ```bash
    tar xzf Katib-<version>-linux-x86_64.tar.gz
    ./Katib/Katib
    ```

    You need GTK 3 and WebKitGTK 4.1 from your package manager. On Fedora that is
    `gtk3 webkit2gtk4.1`.

## Android

1. Download `Katib-android.apk` from the releases page, on the phone or by copying it across.
2. Open it. Android asks you to allow installs from your browser or file manager the first time;
   allow it, then install.
3. Open Katib and type your server's address, such as `192.168.1.20:8420`. It remembers it.

The app opens your server's own interface full screen, so the phone always matches everyone else's
version. To use a different server later, tap the workspace name and choose **Other servers**.

## iPhone and iPad

Apple only lets apps onto a phone through the App Store or Xcode, so there is nothing to download.
Do this instead:

1. Open your Katib server in Safari.
2. Tap the share button, then **Add to Home Screen**.

It runs full screen with its own icon, and edits you make without a signal are sent when it comes
back. This needs an `https` address, which the [Docker setup](deploy.md) gives you. If you have a
Mac with Xcode, you can also build and install the real app — see
[installers/mobile](https://github.com/MergenEnBilge/Katib/tree/main/installers/mobile).

## A server for your team

One line, on any machine with Docker:

```bash
docker run -d --name katib --restart unless-stopped -p 8420:8420 -v katib-data:/data ghcr.io/mergenenbilge/katib:v0.1.0-rc2
```

The tag is a release candidate because that is the newest Katib there is. A `:latest` tag will
appear with the first stable release.

Open `http://localhost:8420`, or the machine's address from another computer. On a Linux server,
this does the same and prints the address for you:

```bash
curl -fsSL https://raw.githubusercontent.com/MergenEnBilge/Katib/main/install.sh | sh
```

[Put Katib online](deploy.md) covers HTTPS, Postgres and Raspberry Pi.

## From the source

You need Python 3.12 or newer, and Node 20 or newer to build the interface once.

```bash
pip install uv
npm install -g pnpm
```

Then, from the folder you downloaded Katib into:

```bash
uv sync
pnpm --dir web install
pnpm --dir web build
uv run katib
```

Your browser opens on Katib at `http://127.0.0.1:8420`.

If your terminal says `uv` is not recognised, `pip` put it somewhere that is not on your PATH. Put
`python -m` in front: `python -m uv run katib`. If you are inside an activated virtual environment,
`uv` is not installed in it, so run `katib` directly.

For a window of its own instead of a browser tab:

```bash
uv sync --extra desktop
uv run katib app
```

### Build an installer yourself

One command, on the kind of machine you want an installer for:

```bash
uv run --extra desktop --group packaging python installers/build.py
```

It builds the interface, freezes the app and wraps it the way your platform expects. The result
lands in `dist/installers`. A Windows installer has to be built on Windows, a macOS one on macOS.
See [installers/README.md](https://github.com/MergenEnBilge/Katib/tree/main/installers) for what
each platform needs.

## The first time you open it

On your own computer, Katib opens straight into your projects. There is nothing to sign in to.

On a shared server, the first person to open the page creates the administrator account. If you
reach the server from outside your own network, Katib asks for a setup code first, so a stranger
cannot claim your server. Find it in the server's log or in `setup-code.txt` in its data folder.

## Try it first

New to labeling? On the home page, choose **Try it with practice pictures**. Katib makes a small
project called *Try Katib* with six pictures, two classes, and one picture already labeled so you
can see what finished work looks like. A guided tour opens right away. It points at each part of the
workspace and asks you to draw your first box. It takes about two minutes, and you can leave at any
point with **Skip the tour**.

The welcome card on the home page keeps a short checklist: create a project, add pictures, add a
class, draw a shape, mark a picture done, export your labels. Each item ticks itself off as you do
it. Hide the card when you no longer need it.

You can replay the tour or make another practice project whenever you like. Choose **Help** in the
sidebar on the home page, or the help button (a question mark) at the top of a workspace.

## Your first project

1. Choose **New project** and give it a name. Pick the kinds of shapes you will draw. You can only
   save the kinds you pick.
2. Choose **Import images**. Upload files from your computer, or **connect a folder** on the computer
   that runs Katib. Connecting reads your photos where they are and never changes them.
3. In the **Classes** tab, add a class such as `car`.
4. Press **B** for the box tool, drag on the image, and release. Every edit saves on its own.
5. Press **Shift+Enter** to mark the image as done and move to the next one.
6. When you are ready, choose **Export**, pick a format, and download a zip file.

Press **?** at any time for a list of every shortcut.

## Making room on screen

The workspace folds away what you are not using, and remembers how you left it.

| Key | What it does |
|-----|--------------|
| `[` | Folds the image list away, or brings it back |
| `]` | Folds the classes and details panel away |
| `\` | Gives the picture the whole window, or puts both panels back |

On the home page, `[` folds the sidebar down to its icons. Each of these has a button too, so you do
not have to remember the keys.

## Where your data lives

Katib keeps its database, thumbnails, uploads and undo history in one folder. Uploaded images are
copied there. Images you connect from a folder are only read, never copied or modified.

| System | Default location |
|--------|------------------|
| Windows | `C:\Users\you\AppData\Local\katib` |
| macOS | `~/Library/Application Support/katib` |
| Linux | `~/.local/share/katib` |
| Docker | The `katib-data` volume, mounted at `/data` |

Change it in **Settings**, then **Storage**, or with `storage.data_dir` in `katib.toml`. See
[Running a server](server.md#settings) for every setting.

## Stopping, upgrading and removing

| | How |
|---|-----|
| Stop it | Close the window, or press Ctrl+C in the terminal. With Docker, `docker stop katib` |
| Upgrade it | Install the new version over the old one. Your data is migrated when Katib starts. With Docker, run the install line again |
| Back it up | **Settings**, then **Backup**, writes a zip you can keep elsewhere. Restore it with `katib restore your-backup.zip` |
| Remove it | Uninstall as you would any app: Add or remove programs on Windows, drag to the bin on macOS, `sudo apt remove katib` on Debian. Your data folder is left alone, so delete it separately if you want it gone |
