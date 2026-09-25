# Images, folders and formats

## Adding images

Choose **Import images** in a project.

**Upload from this device** copies the files into Katib's data folder. Files can be up to 50 MB by default (`limits.max_upload_mb`).

**Connect a folder** reads images where they are, on the computer that runs Katib. Katib walks the folder and everything inside it, and adds each JPEG, PNG, WebP, BMP and TIFF file. It never copies, moves or changes your originals.

Pictures that are already in the project, judged by their content and not their name, are skipped and reported. Files that cannot be read are skipped with a reason.

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

Shapes that a format cannot hold are converted where that is sensible (for example, a polygon becomes its bounding box in YOLO detection) and skipped otherwise. The export report lists every change, so nothing disappears silently.

## Exporting

Choose **Export**, pick a format and which images to include (all, done, or not done). You can copy the images into the export or leave them out.

### Train, validation and test splits

If your images have a saved split, exporting uses it and writes the `train`, `val` and `test` folders your training code expects. Images with no split go with the training images. You can instead make a new split just for that export, or leave the export unsplit. See [Splits](#splits).

### Class order

YOLO uses the position of each class, not its name. If you reorder or rename classes after an export, Katib warns you before the next one that indices will change.

## Duplicates and dataset health

Open **Dataset health** for a report on tiny shapes, duplicate shapes, near-identical photos, images with no shapes and classes with far fewer examples than the rest. See [Class tools and dataset health](classes.md).
