# Install and first project

## What you need

- Python 3.12 or newer
- Node 20 or newer (only to build the interface once)

Install the two helper tools:

```bash
pip install uv
npm install -g pnpm
```

## Run it

From the folder you downloaded Katib into:

```bash
uv sync
pnpm --dir web install
pnpm --dir web build
uv run katib
```

Your browser opens on Katib at `http://127.0.0.1:8420`. Everything is stored in a small local database in your user folder, so there is nothing else to set up.

Prefer a window of its own? Install the desktop extra and use `katib app`:

```bash
uv sync --extra desktop
uv run katib app
```

## Try it first

New to labeling? On the home page, choose **Try it with practice pictures**. Katib makes a small project called *Try Katib* with six pictures, two classes, and one picture already labeled so you can see what finished work looks like. A guided tour opens right away. It points at each part of the workspace and asks you to draw your first box. It takes about two minutes, and you can leave at any point with **Skip the tour**.

The welcome card on the home page keeps a short checklist: create a project, add pictures, add a class, draw a shape, mark a picture done, export your labels. Each item ticks itself off as you do it. Hide the card when you no longer need it.

You can replay the tour or make another practice project whenever you like. Choose **Help** in the sidebar on the home page, or the help button (a question mark) at the top of a workspace.

## Your first project

1. Choose **New project** and give it a name. Pick the kinds of shapes you will draw. You can only save the kinds you pick.
2. Choose **Import images**. Upload files from your computer, or **connect a folder** on the computer that runs Katib. Connecting reads your photos where they are and never changes them.
3. In the **Classes** tab, add a class such as `car`.
4. Press **B** for the box tool, drag on the image, and release. Every edit saves on its own.
5. Press **Shift+Enter** to mark the image as done and move to the next one.
6. When you are ready, choose **Export**, pick a format, and download a zip file.

Press **?** at any time for a list of every shortcut.

## Where your data lives

Katib keeps its database, thumbnails, uploads and undo history in one folder. Uploaded images are copied there. Images you connect from a folder are only read, never copied or modified.

| System | Default location |
|--------|------------------|
| Windows | `C:\Users\you\AppData\Local\katib` |
| macOS | `~/Library/Application Support/katib` |
| Linux | `~/.local/share/katib` |

Change it with `storage.data_dir` in `katib.toml`. See [Running a server](server.md#settings) for every setting.

## Stopping and upgrading

Stop Katib with Ctrl+C in the terminal. To upgrade, download the new version, then run the `uv sync`, `pnpm ... build` and `uv run katib` steps again. Your data is migrated automatically when Katib starts.
