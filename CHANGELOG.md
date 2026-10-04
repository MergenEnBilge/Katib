# Changelog

All notable changes to Katib are listed here, newest first. Each release is also on the
[releases page](https://github.com/MergenEnBilge/Katib/releases).

## 0.7.0

### Labelling text

- A project of text now covers the work people actually do with it: **finding things in the
  words**, **joining them up**, **sorting documents**, and **writing an answer** such as a summary
  or a translation.
- **Relations** join one span to another, with a class of their own, so "Ada" and "Katib" can be
  joined as "works for". A link reads one way round, is listed under the spans, and goes away with
  the span it pointed at.
- Katib now reads and writes the formats text work expects: **CoNLL**, **Hugging Face token
  classification**, **Label Studio**, **BRAT standoff**, and **text with a label** as CSV or JSON
  Lines. The spans file Katib already had is now also written under the names **spaCy** and
  **Prodigy** read, so one file loads in all three.
- Label Studio and BRAT carry the links between spans as well as the spans, so a project can go out
  and come back whole. Exporting links in any other format says how many were left out.
- CoNLL and Hugging Face label whole words rather than characters. A span that stops mid-word is
  stretched to that word's edges, and the export says how many were stretched.
- A file of labelled text can be read into an empty project: the documents are made from the words
  the file carries, instead of the labels being dropped for want of anything to attach them to.

### Choosing what a project is

- A new project asks what you are labelling, pictures or text, and then what the job is, instead of
  offering eight kinds of shape to tick. Each job takes only the tools it needs.
- A project is pictures or text, and refuses the other kind's shapes. Before, ticking "Text spans"
  without clearing the two that came ticked made a project whose import pane offered only
  documents while every picture format vanished from its exports.
- A job for finding objects no longer arrives with the polygon tool as well. Pick **Choose the
  shapes myself** to set them one by one.

### Fixed

- **Labelling spans now works.** A new span stayed picked, and Delete or Backspace anywhere on the
  page removed whatever was picked, so labelling some words and then naming the class threw the
  span away and swallowed the keystroke.
- The canvas sits behind a document so that saving and locks carry on working, but it was still
  taking the document's keys. With a span picked there was no way to move to the next document.
- A text file written on Windows put every span out of place by one character per line before it,
  because of how its line endings were counted.
- Opening a document showed the previous one's words for a moment, and words selected then were
  saved in the wrong place.
- Labelling the same words twice over made a second span on top of the first. It now picks the one
  that is there.
- Below 700 pixels the header hid Import, Export, the split, the team, the class manager, dataset
  health and help, and once a project had a single picture there was no way to reach any of them.
  They now gather behind a **More** menu.
- A project of text opened Export on a format it could not use, which showed an empty box and then
  failed.
- Asking to export into a folder without naming one quietly made a zip instead. Turning that
  setting off again left Export greyed out with the reason hidden.
- Classes can be put in order, which sets the numbers formats such as YOLO write. The export window
  has always said as much; now there is a way to do it.
- Export says when it is waiting for a class, rather than being greyed out with nothing to explain
  it, and offers to open the class manager.
- Train, validation and test shares that did not add up to a hundred were quietly scaled, so
  50/50/50 exported a third each. The window now says what the numbers will become.
- Copying a folder read every picture before sending the first one, to see which were already
  there, with an empty progress bar throughout. It now says what it is doing.
- A failure to check for buckets, or for the folders a project already reads, was reported as there
  being none of either. Both now say so and offer to try again.
- Boxes that take a path on the Katib computer showed a Linux example on a Windows server.
- A failed reservation on an image was passed over in silence unless somebody else held it, which
  left two people editing one image with neither being told.
- A secret key for a bucket is no longer typed in plain sight, and forgetting a bucket asks in a
  window that says what will happen rather than the browser's own box.
- Pre-labelling counts the class names as they are typed and says where their order comes from.
- A project of text was told about YOLO, COCO and Pascal VOC on its labels tab while being offered
  none of them.
- Splitting a project of text into training and validation sets used ratios meant for object
  detection.

## 0.6.0

### Text documents

Katib can now label text, not only pictures. Choose **Text spans** when you create a project and it
holds documents instead of images.

- Add documents from `.txt` and `.md` files, one each, or from a `.jsonl` file with one document
  per line. Spans and tags already in a `.jsonl` line come in with it, and their classes are created.
- Label words by choosing a class and selecting them. Spans can overlap, and space at the edges of a
  selection is left out. Click a span to change its class or remove it.
- Export with **Text spans (JSON Lines)**. Each line holds the words and the spans, so the file
  stands on its own, and it can be imported again.
- Everything else works as it does for pictures: roles, the queue of work, review, splits, comments,
  and 30 days of undo.

### Pictures from cloud storage

- A server can read pictures straight from **Amazon S3, Cloudflare R2, Backblaze B2, MinIO, Google
  Cloud Storage and Azure Blob Storage**, so a dataset already in a bucket does not have to be
  downloaded and uploaded again.
- An administrator adds a bucket under **Settings**, then **Storage**. Katib tries the details first
  and says how many objects it can see.
- In a project, **Import images**, then **Read from the bucket**. You can limit it to names starting
  with something.
- The pictures stay in the bucket. Katib keeps their thumbnails and fetches a picture when somebody
  opens it. Folder names in the bucket set the split.
- Keys are kept in a file only Katib can read, and are never sent back to a browser. Katib only ever
  reads from a bucket, so give it a key that can only read.

### Export to a folder
- Exporting to a folder can **move** the pictures instead of copying them. They go into the
  export folder's `images` folder, and the label files refer to them by name. This needs a typed
  confirmation. Katib keeps reading the pictures from their new place, and if the export fails
  partway, every picture goes back where it was.


- Exports can be written straight into a folder on the Katib computer, as an alternative to a zip.
  The folder must be empty or new, so nothing is overwritten. Only administrators can choose one.

### Faster and clearer imports

- Connecting a folder is about three to four times faster for full-size camera photos, because each
  picture is decoded once instead of twice. Hashes of pictures added from now on are computed the
  same way, so near-duplicate checks still line up with older pictures.
- Connecting a folder now tells you what it found: labels loaded, no labels found, or a dataset that
  could not be read, with the reason.
- A `data.yaml` in a folder above the one you connect is now used, when it lists that folder as a
  split. Classes come from it even when there are no label files yet.

### Labels

- The labels dialog has a **Choose labels** button. It opens the same folder browser as the pictures,
  and it lists label files so you can pick a `data.yaml` or `obj.data` directly. Typing a path still works.
- Administrators, and anyone on a server without accounts, can import labels from any folder they can
  browse to.

### Sharing and uploads

- Scanning the share code with an Android phone opens a page on your Katib with a download
  button. Before, the code pointed straight at the file, which many phone cameras did not offer
  as something to tap.
- Copying a folder into Katib skips pictures the project already has. They are recognised by their
  contents, so a second copy of the same dataset sends nothing for pictures it has already sent.
  Label files are still sent. On a plain http address, where the browser cannot compute checksums,
  everything is sent as before.

### Fixed

- Two people creating a project at the same moment could both be given the same web address for
  it, and the second one saw a server error. Katib now takes the next address along.
- Exporting with **move** could take pictures that another project was also reading. It is now
  refused, and says which project to look at.
- A restored backup left the files holding secrets readable by anyone on the machine, because a zip
  carries no permissions. They are made private again.
- A document with many labelled spans is quicker to draw.

## 0.5.1

### Fixed

- Uploading a model whose class names were stored in an unusual form could fail with an error. Katib
  now ignores names it cannot read and carries on with the model.

### Security

- A review of uploads, sign-in, folder import, file serving and the dependencies found no further
  problems.

### Documentation

- The README and the guides have been rewritten in plainer language, with the steps for each task
  set out in order.
- Each release now has an entry in this changelog.

## 0.5.0

### Security

Update if you run Katib on a computer you also use for browsing.

- Other websites could reach a Katib running on your own computer and send it requests, such as
  a restart or a factory reset. Katib now refuses requests that come from other sites, whether or
  not you are signed in.
- A remote Katib opened in the desktop window could reach the window's own controls and stop the
  server on your computer. Those controls now work only on the window's start page.
- Anyone who owned a project could list the email address of every account. Searching for people
  to add is now limited to administrators. Everyone else types the full email address.
- An invite kept working after the person who sent it lost the right to add people. It now stops
  working.

### Datasets come in as they are

Connect a folder that already holds a dataset, and its pictures, classes, shapes and splits come
in with it. More layouts are recognised now:

- **YOLO:** `data.yaml` files that point at image folders or list files, Roboflow's
  `train/images` and `train/labels` layout, and the older Darknet layout with `obj.data`,
  `obj.names` and `train.txt`. Pose datasets come in as keypoints, and rotated boxes are no longer
  mistaken for polygons.
- **COCO:** one file per split folder, and masks stored as run-length data.
- **Pascal VOC:** `VOCdevkit` folders, with `trainval.txt` used as the training split.
- **LabelMe:** split folders, circles and points.
- **New formats:** CVAT XML, CreateML JSON, mask pictures and class-per-folder image sets.

A file name that appears in two splits, such as `train/a.jpg` and `val/a.jpg`, keeps its labels
in both.

### Connected or copied

Connecting a folder has never copied anything. Uploading a folder does copy it into Katib's own
data folder, and the two used to look the same in the list. Now:

- Each folder is labelled **Read in place** or **Copy in Katib**.
- The upload buttons say **Copy**.
- If pictures are deleted or moved after you connect a folder, Katib tells you and offers to
  take them out of the project.

### Clearer errors

- When the server stops answering, a bar tells you on every page. Your changes are kept, and the
  bar clears itself when the server is back.
- The desktop window goes back to its start page and says why when the server it was showing goes
  away. The start page and the tray both open the server log.
- The tray asks before it stops the server, and shows a message if the server will not start.
- A factory reset that could not delete something now says so in Settings.
- `katib stop` explains when stopping takes a while instead of reporting a failure.

### Setup code

On the computer Katib runs on, the setup code now fills itself in. You can get it from the Katib
window, the tray menu item **Finish setting up Katib**, or `katib setup-code`. Only your own
account can read it on that computer. Anyone setting up from another device still types it in.

### Known limits

- The tray icon on Linux needs AppIndicator support.
- The macOS build has not yet been opened on a Mac.
- The installers are not code-signed, so Windows and macOS warn you the first time.
- The Android app is a WebView around the same interface as the browser.
- Mask pictures can be imported but not exported. Export masks as COCO instead.

## 0.4.0

### The server keeps running when you close the window

On the desktop, the server is now its own program, **Katib Server**. It shows an icon in the
system tray while it runs.

- The window is one way to use it. It finds the running server, or starts one in the background,
  the same way a browser tab or the phone app would.
- Closing the window leaves the server running, so phones and colleagues stay connected.
- Stop the server from the tray menu, from the launcher, or with `katib stop`.
- **Start when I sign in** is in the tray menu. It is off until you turn it on.
- **Restart to apply** works on the desktop now, so you no longer need to close and reopen Katib.

Only one server can run per data folder. A second one will not start, and `katib status` shows
where the first one is answering.

### Teams

- Owners and managers can add someone who already has an account to a project, from the project's
  Team window. You no longer need to send an invite link to a person who has an account.
- Invite links work for people who already have an account. Signed in, the link offers to join you
  to the project. Signed out, it asks you to sign in first.
- Managers can add, change and remove annotators, reviewers and viewers. Owners and managers stay
  with owners.
- Settings, then People, shows which projects each person is on.
- Annotators, reviewers and viewers no longer see Import, Export or the new-class box.
- If you have no projects yet, Katib tells you to ask whoever runs the server to add you.
- A project can no longer lose its last owner.

### Other changes

- About credits the author and links to the source code. Everyone can open it now, not only
  administrators.
- Deleting a project is done from its card in the project list.

### Known limits

- On Linux the tray icon needs AppIndicator support. GNOME gets it through an extension. Without
  it the server still runs, and the launcher can stop it.
- The macOS build has not yet been opened on a Mac.
- The installers are not code-signed.
- The Android app is a WebView around the same interface as the browser.

## 0.3.1

A small release that fixes the Share window and tightens a few security checks.

### Fixed

- The desktop Share window gave out a port that nothing was listening on. It now uses the port
  shown in Settings.
- The desktop app can connect to a Katib that someone else is already running. The launcher offers
  **Run my own** or a server address, the same way a browser would.

### Security

- A saved server address in the desktop launcher was not escaped, so a crafted address could have
  run a script. It is escaped now.
- Checking whether an account was locked out could leave a record behind even with no failed
  attempts. Those records are no longer kept.
- Restoring a backup checked for free disk space only after unpacking part of it. It now checks
  first.
- The Android app allowed a secure page to load insecure content. It no longer does.
- The build pipeline's third-party actions are pinned to exact versions, and its workflow asks for
  the smallest permissions it needs.
- A `secret_key` setting that was never used has been removed.

These were found in a review of the code, not by anyone running into them. The details are in the
[security notes](docs/security.md).

## 0.3.0

### Fixed

- Turning on **Everyone on my network** in the desktop app's Settings had no effect. The window now
  listens on the address you chose.
- The guided tour lost track on a phone, where some steps point at things hidden in a side panel.
  It opens the panel it needs, and skips a step when there is nothing to point at.
- Click to select could return the whole picture when it was not sure of anything. That now counts
  as no answer.
- A downloaded model's files could confuse the model list. Replacing a model file by hand also left
  the old download marked as installed.
- A factory reset could report success while a locked file, usually the database, was left in
  place.
- On a phone, scrolling to the end of a list could show the browser's own bounce effect, and the
  keyboard resized the window unpredictably.

### Added

- **Download a Segment Anything model by name** from Settings, then Model help. MobileSAM and ViT-B
  are checked against a fixed hash before they are used.
- **Delete a project or manage its team** from its card in the project list.
- **Factory reset** under Settings, then Storage. It asks you to type RESET and shows what it will
  remove first.

### Known limits

- The Android app is a WebView around the same interface as the browser.
- The installers are not code-signed.

## 0.2.0

This release is about getting your pictures into Katib when it runs somewhere that cannot see
them directly, such as Docker.

### Added

- **Upload a folder.** Next to **Connect a folder**, you can send a whole folder from the browser,
  including its subfolders and any label files. Each file uploads on its own, so you can watch the
  progress. If the folder already holds a dataset, its classes, splits and shapes are read at the
  same time.
- Two limits are now settings under Settings, then Limits: the largest single file (100 MB by
  default) and the largest folder upload (20,000 files by default).

### Fixed

- When Katib could not see a folder, the error told you to ask an administrator. It now explains
  that the folder is not visible to the server and shows the `-v` flag to add when starting Docker.

### Known limits

- Click to select has not been run against real SAM weights in this release.
- The installers are not code-signed.

## 0.1.0

The first full release. Katib labels images for computer vision on hardware you control. It starts
with one command on a laptop, and it grows into a server that a team can sign into.

### What is in it

- Six kinds of shape: boxes, polygons, rotated boxes, keypoints with skeletons, brush masks and
  whole-image tags, plus text for captions.
- Keyboard shortcuts for almost everything. Changes save as you make them.
- Class tools that rename, merge and delete across a project, with a preview first and 30 days of
  undo.
- Dataset health checks for tiny shapes, duplicate shapes, near-identical photos and unbalanced
  classes.
- Import and export for YOLO, COCO, Pascal VOC, LabelMe and JSON Lines, with train, validation and
  test splits kept.
- Accounts, invite links, five roles, review, and per-image locks.
- Settings for everything, with backups and restore.
- A practice project and a guided tour for new users.
- Draft boxes from your own ONNX detection model.
- A layout that works on a phone, including an Android app.

### Click to select

Give Katib a Segment Anything model, and clicking an object outlines it. Shift-click adds to the
selection, and Ctrl-click takes away. You supply the two ONNX files under Settings, then Model help.

### Accounts you create yourself

Under Settings, then People, administrators can add someone with an email address and a password,
make them an administrator, reset a password, or turn an account off. Everyone can change their own
password, which also signs out their other devices.

### Known limits

- The installers are not code-signed.
- The Android app is signed with a debug key unless you configure a release keystore.
- There is no iPhone app. Add your server to the home screen from Safari.
- The interface is in English.

## 0.1.0-rc3

- The Android app can connect to a server on your network over plain http.
- In Docker, Katib shows the address your browser used, not the container's address.
- Invite links use an address other people can open, not `localhost`.
- A message after saving in Settings no longer blocks the Save button on a phone.
- Project cards show the first picture in the project.
- The Android app needs Android 8 or newer.

## 0.1.0-rc2

- Project cards show the first picture in the project.
- The Linux build runs on Ubuntu 22.04, Debian 12 and Raspberry Pi OS (bookworm). The `.deb` checks
  its C library version, so apt refuses to install it where it cannot run.
- The Linux app opens its window. The first pre-release could install but not open a window.
- Side panels can be folded away with a button or a key, and stay folded next time.
- The zoom readout on the canvas has one place now.

## 0.1.0-rc1

The first pre-release build.
