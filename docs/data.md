# Images, folders and formats

## Adding images

Choose **Import images** in a project. There are two ways in, and which one is faster depends on
where your pictures already are relative to Katib.

**Connect a folder** reads images where they are, on the computer that runs Katib, and never
copies, moves or changes your originals. This is the one to want: nothing is duplicated, and a
folder of any size connects in an instant because Katib is only reading a directory listing, not
transferring the pictures themselves. The catch is that Katib has to be able to see that folder
itself. On your own machine that is true by default. In a container it usually is not — a
container only sees folders that were mounted into it when it started, which is what `-v` on
`docker run`, or a line under `volumes` in a compose file, does. Connecting a folder from inside
Katib cannot reach anything beyond that, however correct the path looks, because the container's
filesystem is not your computer's.

**Upload a folder**, or its neighbour **Upload pictures and labels** for a handful of loose files,
sends everything over the browser instead, and copies it into Katib's data folder. This is what to
reach for when Katib cannot see your files directly — there is no way around the copy in that
case, because the browser and the server genuinely do not share a filesystem; sending the bytes is
the only path between them. It works everywhere, though, which "Connect a folder" cannot promise.
A whole folder brings its subfolders, and any `data.yaml`, labels or other annotation files
inside, along with it. Pick loose files instead of a folder and the same thing happens without
one: a picture and its label file are matched up by name whether or not they shared a folder,
read the same way as [an existing dataset](#reading-an-existing-dataset) below. Either way, the
upload goes up one file at a time, so you can watch it happen and see which
file is going up right now, rather than stare at a spinner that gives no sign of life until a
folder of any real size finishes. Files can be up to 100 MB by default (`limits.max_upload_mb`),
and a folder up to 20,000 files (`limits.max_folder_upload_files`) — both are settings, so raise
them under **Settings**, then **Limits**, if your pictures or your datasets are bigger than that.

Pictures that are already in the project, judged by their content and not their name, are skipped and reported. Files that cannot be read are skipped with a reason.

!!! tip "In Docker, mounting is worth doing"

    If your pictures live on the same machine Docker runs on, mounting them (see [Put Katib
    online](deploy.md)) and using **Connect a folder** is worth the one-time setup for anything
    past a few dozen images — nothing is copied, and a folder of any size connects instantly.
    Uploading is for when that is not possible, or the pictures are on a different machine
    entirely, such as the phone or laptop you are sitting at.

### Reading an existing dataset

Connecting a folder that already looks like a labelled dataset — a `data.yaml` and `labels` folder, a COCO `annotations.json`, Pascal VOC XML, or LabelMe JSON — picks up more than the pictures. Katib recognizes the layout, reads the split each image belongs to from the folder it is in (`train`, `val` or `test`), and imports its classes and shapes in the same step. This works for every format Katib can read, not only YOLO. Nothing is forced on you: a plain folder of photos with no annotation files behaves exactly as before, and you can always run **Import labels** yourself afterward with a specific format if the guess was wrong or you want to add a second label set.

### Keeping a folder up to date

A connected folder stays connected. When you add photos to it later, open **Import images** and press the refresh button next to the folder. Only the new pictures are added. Disconnecting a folder keeps the images already in the project.

### Who can connect a folder

- On a single-person install (`auth.mode = "none"`), you can browse and connect any folder.
- On a shared server, only administrators can browse and connect new folders. Everyone with permission to manage a project can import from folders that are already connected.
- You can allow folders ahead of time in `katib.toml`:

```toml
[storage]
allowed_import_roots = ["/data/photos"]
```

Katib only reads inside folders it was allowed to use, and it checks again every time it serves a picture.

## Importing labels

Add your images first. Then choose **Import**, then **Labels**, and give the path to a dataset folder or file. Katib detects the format, or you can choose one from the list.

Labels are matched to images by file name. If two images have the same name, the label file is skipped and reported. Pictures that already have shapes are left alone, so importing the same file twice never doubles your labels. Class names match your existing classes by name or by an earlier name. Unknown names become new classes.

Every import ends with a report of what was added and what was skipped, and why.

## Splits

A split says which images are for training, which are for checking progress (validation), and which are held back for the final test. Katib keeps the split on each image, so it is the same every time you export.

### Picking up an existing split

When your data already comes divided, Katib notices and keeps it:

- **Folders.** Images inside folders called `train`, `val`, `valid`, `validation` or `test` join that split. This works when you connect a folder and when you import labels.
- **YOLO.** Labels in `labels/train`, `labels/val` and so on, and the `train.txt` and `val.txt` lists named in `data.yaml`.
- **COCO.** A file such as `instances_train2017.json` puts its images in the train split. A folder with one file per split is read as a whole.
- **Pascal VOC.** The lists in `ImageSets/Main`.

### Dividing your own images

Choose **Train, validation and test** in the toolbar (the shuffle icon). The bar shows how many images are in each split now.

1. Pick the kind of dataset. Katib fills in a ratio that suits it, for example 80/10/10 for object detection. Change the numbers to whatever you like.
2. Use **New shuffle** for a different arrangement, or keep the seed to get the same one again.
3. Tick **Keep rare classes in every split** so a class with few examples is not lost from validation or test.
4. Tick **Only place images that have no split yet** to leave existing splits alone. This is handy after adding more photos.
5. Read the preview line, then choose **Split images**. Reshuffling images that already have a split asks you to confirm first.

Every shuffle can be undone from **History** for 30 days. To move a single image, use the **Split** menu above the tabs on the right. The image list can be filtered by split.

## Formats

| Format | Reads and writes | Notes |
|--------|------------------|-------|
| YOLO detection | Boxes | `data.yaml` or `classes.txt`, one `.txt` per image |
| YOLO segmentation | Polygons | Boxes are written as four-point polygons |
| YOLO oriented boxes | Rotated boxes | Four corners per line |
| COCO | Boxes, polygons, keypoints | Rotated boxes are written as polygons. Run-length masks are not read yet |
| Pascal VOC | Boxes | One XML file per image |
| LabelMe | Boxes and polygons | One JSON file per image |
| Tags and text (JSON Lines) | Tags, captions, text in shapes, and every shape kind | One `metadata.jsonl` file. Loads in Hugging Face |

### Tags and text

The JSON Lines format is the one to use for image tags, captions and text found in pictures. Each line describes one image:

```json
{"file_name": "images/train/a.jpg", "width": 640, "height": 480, "split": "train",
 "tags": ["street"], "text": "A red bicycle by a wall.", "texts": ["A red bicycle by a wall."],
 "regions": [{"label": "sign", "type": "box", "geometry": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}, "text": "STOP"}]}
```

`text` is the first caption and `texts` lists them all. `regions` holds shapes with their coordinates as fractions of the image, and the words written inside them. Include the image files in the export and the folder loads straight into Hugging Face with `load_dataset("imagefolder", data_dir=...)`. The same file can be imported back.

Shapes that a format cannot hold are converted where that is sensible (for example, a polygon becomes its bounding box in YOLO detection) and skipped otherwise. The export report lists every change, so nothing disappears silently.

## Exporting

Choose **Export**, pick a format and which images to include (all, done, or not done). You can copy the images into the export or leave them out.

Every format on the list is covered by a test that exports a project holding one of each shape kind, unpacks the zip, imports it into an empty project and checks the shapes came back. That runs on every change, so an export that cannot be read again does not reach you.

### Train, validation and test splits

If your images have a saved split, exporting uses it and writes the `train`, `val` and `test` folders your training code expects. Images with no split go with the training images. You can instead make a new split just for that export, or leave the export unsplit. See [Splits](#splits).

### Class order

YOLO uses the position of each class, not its name. If you reorder or rename classes after an export, Katib warns you before the next one that indices will change.

## Duplicates and dataset health

Open **Dataset health** for a report on tiny shapes, duplicate shapes, near-identical photos, images with no shapes and classes with far fewer examples than the rest. See [Class tools and dataset health](classes.md).
