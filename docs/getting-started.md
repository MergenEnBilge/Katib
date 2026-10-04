# Getting started

This guide shows you how to install Katib, make your first project and label your first picture.

## Choose how to install

| If you want | Go to | It takes |
|-------------|-------|----------|
| Katib on your own computer | [Windows](#windows), [macOS](#macos) or [Linux](#linux) | About 2 minutes |
| Katib for your team, on a server | [A server for your team](#a-server-for-your-team) | About 5 minutes |
| Katib on your Android phone | [Android](#android) | About 2 minutes |
| Katib on your iPhone or iPad | [iPhone and iPad](#iphone-and-ipad) | About 1 minute |
| To change Katib itself | [From the source](#from-the-source) | About 5 minutes |

Your pictures and labels stay on your own computer or server. The only thing Katib downloads from
the internet by itself is a model that you ask for by name in Settings. You can skip that too.

!!! note "Version numbers"

    The commands in this guide use version `0.6.0`, the latest release. To install a newer one,
    change the number. Everything else stays the same. All releases are listed on the
    [releases page](https://github.com/MergenEnBilge/Katib/releases).

!!! warning "Copying commands on Windows"

    Copy each command as one line. Some guides split long commands across several lines with a
    `\` at the end. Mac and Linux terminals accept that, but PowerShell does not, and it fails with
    `invalid reference format`.

## Windows

1. Download `Katib-<version>-windows-setup.exe` from the
   [releases page](https://github.com/MergenEnBilge/Katib/releases).
2. Open the file. It installs for your user account only, so you do not need an administrator
   password.
3. Windows may say it does not recognise the publisher, because the installer is not code-signed
   yet. Choose **More info**, then **Run anyway**.
4. Start Katib from the Start menu or the desktop shortcut.

When Katib opens, you see a small start screen. You can:

- **Open Katib on this computer.** This starts the Katib server in the background, if it is not
  already running, and opens the window.
- **Connect to another Katib.** Type the address of a Katib someone else is running, and open it
  in the window.

The window and the server are separate. The server keeps your projects and answers every device
that connects to it. The window is just one of those devices, like a browser tab. A Katib icon
appears in the system tray, in the corner of the taskbar near the clock.

Closing the window does not stop the server, so phones and colleagues stay connected. To stop the
server, right-click the tray icon and choose **Stop the server**, or use the stop button on the
start screen.

To have the server start every time you sign in, turn on **Start when I sign in** in the tray menu.
It is off by default.

By default, the server only answers on your own computer. To let other people on your network use
it, go to **Settings**, then **Sharing**, choose **Everyone on my network**, and restart Katib from
the button Settings offers.

## macOS

1. Download `Katib-<version>-macos.dmg` from the releases page.
2. Open the file and drag **Katib** into **Applications**.
3. The first time you open it, right-click the app and choose **Open**, then choose **Open** again
   in the box that appears. macOS blocks a normal double-click because the app is not signed yet.
   You only need to do this once.

## Linux

The Linux package is built on Ubuntu 22.04. It runs on Ubuntu 22.04, Debian 12, Raspberry Pi OS
bookworm and newer versions. On an older system, use Docker instead.

=== "Debian, Ubuntu and Raspberry Pi OS"

    ```bash
    sudo apt install ./katib_<version>_amd64.deb
    ```

    The package installs the two libraries Katib needs for its window, GTK and WebKitGTK. Then open
    **Katib** from your applications menu, or run `katib-app` in a terminal.

=== "Other distributions"

    ```bash
    tar xzf Katib-<version>-linux-x86_64.tar.gz
    ./Katib/Katib
    ```

    You need GTK 3 and WebKitGTK 4.1 from your package manager. On Fedora, install
    `gtk3` and `webkit2gtk4.1`.

## Android

1. On a computer running Katib, click the workspace name at the bottom of the sidebar. Point your
   phone's camera at the code labelled **Get the app** to download it. You can also download
   `Katib-android.apk` from the releases page.
2. Open the file. The first time, Android asks you to allow installs from your browser or file
   manager. Allow it, then install the app.
3. Open Katib and tap **Scan the code instead**. Point the camera at the code labelled with your
   server's address. You can also type the address, such as `192.168.1.20:8420`. Katib remembers
   the server after that.

You need Android 8 or newer.

The app shows your server's web pages in full screen, so your phone always runs the same version as
everyone else. To switch to another server later, tap the workspace name and choose **Other
servers**.

## iPhone and iPad

Apple only allows apps onto an iPhone or iPad through the App Store, so Katib is added from Safari
instead:

1. Open your Katib server in Safari.
2. Tap the share button, then tap **Add to Home Screen**.

Katib then opens full screen with its own icon. If the connection drops, you can keep working, and
your changes are sent when you are back online.

Your server needs an `https` address for this to work. The [Docker setup](deploy.md) includes one.

## A server for your team

Run this one line on any computer with Docker installed:

```bash
docker run -d --name katib --restart unless-stopped -p 8420:8420 -v katib-data:/data ghcr.io/mergenenbilge/katib:v0.6.0
```

The version number in the command means Katib only updates when you change it. If you want the
newest version every time, use `:latest` in place of the number. See [Putting Katib online](deploy.md)
for HTTPS, Postgres and Raspberry Pi setups.

Then open `http://localhost:8420` in a browser. From another computer, use the server's address
instead, such as `http://192.168.1.20:8420`.

On a Linux server without Docker, this script installs Katib and prints the address:

```bash
curl -fsSL https://raw.githubusercontent.com/MergenEnBilge/Katib/main/install.sh | sh
```

## From the source

You need Python 3.12 or newer, and Node 20 or newer.

```bash
pip install uv
npm install -g pnpm
```

Then, in the folder you downloaded Katib into, run:

```bash
uv sync
pnpm --dir web install
pnpm --dir web build
uv run katib
```

Your browser opens Katib at `http://127.0.0.1:8420`.

If your terminal says that `uv` is not recognised, run the same commands with `python -m` in front
of `uv`, for example `python -m uv run katib`.

To open Katib in its own window instead of a browser tab, install the desktop extras first:

```bash
uv sync --extra desktop
uv run katib app
```

### Build an installer yourself

Run this on the kind of computer you want the installer for. A Windows installer has to be built on
Windows, and a macOS one on macOS.

```bash
uv run --extra desktop --group packaging python installers/build.py
```

The installer appears in `dist/installers`. See
[installers/README.md](https://github.com/MergenEnBilge/Katib/tree/main/installers) for what each
platform needs.

## Your first sign-in

On your own computer, Katib opens straight to your projects. There is no account to create.

On a shared server, the first person to open the page creates the administrator account. That
account runs the server. Because of that, Katib asks for a **setup code** before it creates the
first account, if other people can reach the server.

- **On the computer Katib runs on**, you do not need to look up the code. Open Katib from its
  window, or choose **Finish setting up Katib** from the tray menu. The code is filled in for you.
- **From a terminal**, run `katib setup-code`. It prints the code and a link that fills it in.
- **In Docker**, run `docker logs katib`, or `docker exec katib cat /data/setup-code.txt`.
- **From another device**, type the code in the box. The code stops working once the first account
  exists.

A Katib that only answers on its own computer does not ask for a code, because nobody else can reach
it. In Docker, Katib always asks.

## When something goes wrong

If the server stops answering, every page shows a bar at the top saying so. Your unsaved changes
are kept. Katib reconnects by itself once the server is back.

The Katib window returns to its start screen and tells you what happened. Choose **Show the server's
log** to open the log file, which lists the error.

From a terminal, `katib status` tells you whether the server is running and where it is. `katib stop`
stops it.

## Try Katib with practice pictures

If you are new to labelling, start here. On the home page, choose **Try it with practice pictures**.
Katib creates a small project called *Try Katib*. It contains six pictures, two classes, and one
picture that is already labelled, so you can see what finished work looks like.

A short guided tour starts right away. It points to each part of the screen and asks you to draw
your first box. It takes about two minutes. You can stop at any time with **Skip the tour**.

The welcome card on the home page has a checklist: create a project, add pictures, add a class, draw
a shape, mark a picture as done, and export. Each step is ticked off when you finish it. Hide the card
when you no longer need it.

To run the tour again or make another practice project, choose **Help** in the sidebar on the home
page. You can also use the question mark button at the top of a project.

## Your first project

1. Choose **New project**, and give it a name. Pick the kinds of shapes you need, such as boxes or
   polygons. The toolbar only shows the kinds you choose.
2. Choose **Import images**. You can upload files from your computer, or connect a folder on the
   computer that runs Katib. Connecting a folder reads your pictures where they are. Katib never
   changes them.
3. Open the **Classes** tab and add a class, such as `car`.
4. Press **B** to select the box tool. Drag across the picture to draw a box. Katib saves every
   change as you make it.
5. Press **Shift+Enter** to mark the picture as done and move to the next one.
6. When you are finished, choose **Export**, pick a format, and download the zip file.

Press **?** at any time to see every keyboard shortcut.

## Making more room on screen

The workspace folds away the panels you are not using, and remembers how you left them.

| Key | What it does |
|-----|--------------|
| `[` | Hides or shows the picture list |
| `]` | Hides or shows the classes and details panel |
| `\` | Gives the picture the whole window, or brings both panels back |

On the home page, `[` shrinks the sidebar to icons. Each of these also has a button, if you prefer
to click.

## Where your data is kept

Katib keeps everything in one data folder: the database, thumbnails, uploaded pictures and undo
history. Uploaded pictures are copied into this folder. Pictures you connect from a folder are only
read, never copied or changed.

| System | Default location |
|--------|------------------|
| Windows | `C:\Users\you\AppData\Local\katib` |
| macOS | `~/Library/Application Support/katib` |
| Linux | `~/.local/share/katib` |
| Docker | The `katib-data` volume, mounted at `/data` |

To change the location, go to **Settings**, then **Storage**. You can also set `storage.data_dir` in
`katib.toml`. See [Running a server](server.md#settings) for every setting.

## Stopping, updating and removing Katib

| Task | How |
|------|-----|
| Stop Katib | Stop the server from the tray menu, or run `katib stop`. With Docker, run `docker stop katib` |
| Update Katib | Install the new version over the old one. Your data is updated when Katib starts. With Docker, run the install command again with the new version number |
| Back up your data | Go to **Settings**, then **Backup**. Katib saves a zip file you can keep somewhere safe. To restore it, stop Katib and run `katib restore your-backup.zip` |
| Remove Katib | Uninstall it the usual way for your system. Your data folder is kept, so delete it yourself if you no longer need it |
