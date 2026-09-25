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

Turn on splits and set the ratios. Images are assigned by a seeded shuffle, so the same seed gives the same split. **Stratify** keeps the class mix similar across the splits.

### Class order

YOLO uses the position of each class, not its name. If you reorder or rename classes after an export, Katib warns you before the next one that indices will change.

## Duplicates and dataset health

Open **Dataset health** for a report on tiny shapes, duplicate shapes, near-identical photos, images with no shapes and classes with far fewer examples than the rest. See [Class tools and dataset health](classes.md).
