# Katib

Katib is an annotation tool for computer vision. You draw shapes on images, organize them into classes, and export the result in the format your training code expects.

It runs on your own machine. Start it on a laptop with one command, or on a server that a whole team shares. Your images stay on your hardware, and nothing is sent anywhere unless you set that up.

## Where to start

- **Just want to try it?** [Install and first project](getting-started.md) takes about five minutes.
- **Labeling a lot of images?** Read [Drawing and shortcuts](drawing.md). The keyboard makes it much faster.
- **Have data already?** [Images, folders and formats](data.md) covers connecting a folder of photos and importing existing labels.
- **Setting it up for a team?** [Working together](teams.md) and [Running a server](server.md).
- **Want to script it?** [REST API and Python client](automation.md).

## What it can do

| | |
|-|-|
| Shapes | Boxes, polygons, rotated boxes, keypoints, brush masks and whole-image tags |
| Classes | Rename, merge and delete with a preview and 30 days of undo |
| Data | YOLO (detection, segmentation, rotated boxes), COCO with keypoints, Pascal VOC and LabelMe, with train, validation and test splits |
| Quality | Finds tiny and duplicate shapes, near-identical photos and unbalanced classes |
| Teams | Invites, five roles, a task queue, review and live presence |
| Devices | Desktop, tablet and phone. Installable, and keeps working when the signal drops |
| Help | Draft boxes from your own detection model, and outline objects with a magic wand |

## What it does not do

Katib is deliberately small. It does not track objects through video, label text, audio or 3D data, or sync between separate servers. It has no built-in single sign-on or billing.
