# Katib documentation

Katib is an annotation tool for computer vision. You draw shapes on pictures, sort them into classes,
and export the labels in the format your training code expects.

Katib runs on your own computer, so your pictures stay where they are. You can start it on a laptop
with one command, or run it on a server that your whole team uses.

## Where to start

- **Want to try it first?** [Getting started](getting-started.md) takes about five minutes.
- **Labelling a lot of pictures?** [Drawing and shortcuts](drawing.md) shows the keys that make it faster.
- **Already have a dataset?** [Pictures, folders and formats](data.md) explains how to bring it in and
  take it out again.
- **Setting Katib up for a team?** Read [Working together](teams.md) and [Running a server](server.md).
- **Putting Katib on the internet?** Read [Security](security.md) first, then [Putting Katib where your team can reach it](deploy.md).
- **Writing scripts?** The [REST API and Python client](automation.md) cover everything the app can do.

## What Katib can do

| Area | Details |
|------|---------|
| Shapes | Boxes, polygons, rotated boxes, keypoints, brush masks and whole-picture tags |
| Text | Spans of words in a document, relations joining them, labels for a whole document, and written answers |
| Classes | Rename, merge and delete across a project. Preview first, and undo for 30 days |
| Picture datasets | YOLO, COCO, Pascal VOC, LabelMe, CVAT, CreateML, class folders and JSON Lines, with train, validation and test splits |
| Text datasets | CoNLL, Hugging Face token classification, spaCy, Prodigy, Label Studio, BRAT and plain CSV |
| Quality checks | Finds tiny and duplicate shapes, near-identical pictures and unbalanced classes |
| Teams | Invite links, five roles, a queue of pictures for each annotator, review, and a view of who is online |
| Devices | Works in a browser on desktop, tablet and phone. Can be added to a phone's home screen. Android app included |
| Help with drawing | A magic wand that needs no model, click to select with a Segment Anything model, and draft boxes from your own detector |

## What Katib does not do

Katib works with still pictures and text documents. It does not track objects through video, and it
does not label audio or 3D data. It does not sync between separate servers, and it has no built-in single sign-on or
billing.

## Other documents

- [How Katib is built](internals.md) describes the code, for anyone who wants to change it.
- [Contributing](contributing.md) explains how to set up a development environment and run the checks.
- [Changelog](https://github.com/MergenEnBilge/Katib/blob/main/CHANGELOG.md) lists what changed in each release.
