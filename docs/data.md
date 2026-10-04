# Pictures, folders and formats

This guide covers how to bring pictures and labels into Katib, how splits work, and how to export your
work.

## Adding pictures

Choose **Import images** in a project. You have two options:

- **Connect a folder** reads pictures where they are, on the computer that runs Katib. Katib does
  not copy, move or change them. Connecting is quick even for a large folder, because Katib only
  reads the list of files.
- **Copy a folder** sends the folder from your browser to Katib, and Katib keeps a copy in its data
  folder. Use this when Katib cannot see your files. Copy pictures and labels does the same for a few
  loose files.

Choose **Connect a folder** when you can. It uses no extra disk space, and your originals stay put.

### Why Katib sometimes cannot see your folder

Katib can only connect to folders on the computer where it runs. On your own computer, that is
everything. In Docker, the container can only see the folders you mounted when you started it. Add a
mount with `-v` in the `docker run` command, or a line under `volumes` in a compose file. A folder
that is not mounted cannot be connected, even if you type the right path.

If you cannot mount the folder, use **Copy a folder** instead.

### What a copied folder brings with it

When you copy a folder, its subfolders come with it. So do any `data.yaml` files, label files and
other annotation files inside. If you pick loose files, Katib matches each picture to its label file
by name. Either way, the upload runs one file at a time, and you can see which file is going up now.

Files can be up to 100 MB each by default, and a folder can hold up to 20,000 files. Both limits can
be raised under **Settings**, then **Limits**.

Katib skips pictures that are already in the project. It recognises them by their content, not their
name. Files it cannot read are skipped, and the import report says why.

### Folder labels

The list of folders shows how each one was added:

- **Read in place** means the folder is connected and nothing was copied.
- **Copy in Katib** means the folder was copied into Katib's data folder.

Choose the refresh button next to a connected folder to add any new pictures. Katib also counts
pictures you deleted, renamed or moved since the last time. You can then take those out of the
project, along with any shapes drawn on them. Nothing on your disk is changed.

Disconnecting a folder keeps the pictures that are already in the project.

!!! tip "Docker users"

    If your pictures are on the same machine that runs Docker, mount that folder and use
    **Connect a folder**. It takes a little setup once, and then it works well for any number of
    pictures. Use **Copy a folder** when the pictures are on another machine, such as the laptop you
    are working from.

### Pictures in a cloud bucket

Katib can read pictures straight from cloud storage, so a dataset already in a bucket does not have
to be downloaded and uploaded again.

Supported services:

| Service | What to enter |
|---------|---------------|
| Amazon S3 | The bucket, an access key and secret, and the region |
| Cloudflare R2, Backblaze B2, MinIO | The same, plus the service's address |
| Google Cloud Storage | The same, with `https://storage.googleapis.com` as the address, and an HMAC key from its interoperability settings |
| Azure Blob Storage | The container, the storage account's name, and the account key |

An administrator sets a bucket up once, under **Settings**, then **Storage**, then **Add a bucket**.
Katib tries the details before it saves them and says how many objects it could see, so a wrong key
or region shows up straight away.

Then, in a project, choose **Import images** and **Read from the bucket**. You can limit it to names
starting with something, such as `datasets/street/`.

**The pictures stay in the bucket.** Katib keeps each one's thumbnail, so lists stay quick, and
fetches the picture itself when somebody opens it, keeping a copy in a cache that is safe to delete.
Folder names in the bucket set the split, the same as a folder on disk, so `train/` and `val/` are
picked up.

Give Katib a key that can only read. It never writes to a bucket.

### Who can connect folders

- On your own computer, with accounts turned off, you can connect any folder.
- On a shared server, only administrators can browse for and connect new folders. Anyone who can
  manage the project can import from folders that are already connected.
- To allow certain folders in advance, list them in `katib.toml`:

```toml
[storage]
allowed_import_roots = ["/data/photos"]
```

Katib only reads from folders on this list, and it checks again each time it shows a picture.

## Importing labels

Add your pictures first. Then choose **Import**, then **Labels**, and give the path to a dataset folder
or file. Katib guesses the format. You can also choose one from the list.

Katib matches each label to a picture by file name. Some datasets have the same name in two splits,
such as `train/a.jpg` and `val/a.jpg`. In that case Katib uses the split and the folder to decide
which picture a label belongs to. If it still cannot decide, it skips the label and tells you.

If the dataset states which split an image belongs to, Katib uses that. It does not use its own guess.

Pictures that already have shapes are left alone. Importing the same file twice does not double your
labels. Class names match your existing classes by name, or by an earlier name. Any class that is new
to the project is added.

Every import ends with a report that lists what was added and what was skipped, with the reason.

## Splits

A split says whether a picture is used for **training**, for **validation** (checking progress while
you train), or kept for a final **test**. Katib saves the split with each picture, so exports stay the
same each time.

### Splits that come with your data

Katib keeps the splits that your dataset already has:

- **Folders.** Pictures inside a folder called `train`, `val`, `valid`, `validation` or `test` go into
  that split. This works when you connect a folder and when you import labels.
- **YOLO.** Katib reads the image folders or list files that `data.yaml` names for `train`, `val` and
  `test`. It also reads labels in `labels/train` or `train/labels`, and Darknet's `train.txt` and
  `valid.txt`.
- **COCO.** A file such as `instances_train2017.json` puts its pictures in the training split. So does
  a file inside a `train` folder. A folder with one file per split is read as a whole.
- **Pascal VOC.** Katib reads the lists in `ImageSets/Main`. If there are no separate lists, the
  `trainval.txt` file is used for training.
- **CVAT, LabelMe, CreateML and class folders.** Katib reads CVAT's subsets, and the split folders
  the files are in.

### Making a new split

Choose **Train, validation and test** in the toolbar, the shuffle icon. The bar shows how many pictures
are in each split.

1. Choose the kind of dataset. Katib fills in a sensible ratio, such as 80/10/10 for object detection.
   Change the numbers if you want.
2. Choose **New shuffle** for a different arrangement. The seed number makes a shuffle repeatable, so
   the same seed gives the same result.
3. Tick **Keep rare classes in every split** if a class has few examples. This makes sure the class
   still appears in the validation and test sets.
4. Tick **Only place pictures that have no split yet** to leave existing splits alone. This is useful
   after you add more pictures.
5. Check the preview, then choose **Split images**. If pictures already have a split, Katib asks you to
   confirm before it changes them.

You can undo any shuffle in **History** for 30 days. To move one picture to another split, use the
**Split** menu above the tabs on the right. You can also filter the picture list by split.

## Formats

Katib reads and writes these formats. Read-only formats can be imported but not exported.

| Format | Reads | Writes | How Katib recognises it |
|--------|-------|--------|-------------------------|
| YOLO detection | Boxes | Yes | A `data.yaml` file that names the image folders or list files for `train`, `val` and `test`. Roboflow's `train/images` and `train/labels` folders. The older Darknet files `obj.data`, `obj.names`, `train.txt` and `valid.txt`. Labels sit beside the pictures |
| YOLO segmentation | Polygons | Yes | Same as detection, with a polygon on each line |
| YOLO oriented boxes | Rotated boxes | Yes | Same as detection, with four corner points on each line |
| YOLO pose | Keypoints | Yes | Same as detection, with `kpt_shape` set in `data.yaml` |
| COCO | Boxes, polygons, keypoints, masks | Yes | One file for the whole dataset, a file for each split such as `instances_train2017.json`, or Roboflow's `train/_annotations.coco.json` |
| Pascal VOC | Boxes | Yes | `Annotations` and `ImageSets/Main` folders, including inside `VOCdevkit/VOC2012` |
| LabelMe | Boxes, polygons, circles, points | Yes | One JSON file per picture, also inside split folders. Circles come in as polygons, and points as keypoints |
| CVAT for images | Boxes, rotated boxes, polygons, points, tags | Yes | An `annotations.xml` file. CVAT's subsets become splits |
| CreateML | Boxes | Yes | One JSON file per split, as Roboflow exports it. Add the pictures first, because the file has no picture sizes |
| Mask pictures (PNG) | Masks | No | A `masks` or `SegmentationClass` folder with PNG files named like the pictures. A `classes.txt` or `labelmap.txt` file says which value or colour is which class |
| Class folders | Tags | Yes | Pictures sorted into folders named after their class, such as `train/cat/1.jpg`. Katib only finds this format under split folders. Otherwise choose it by hand |
| JSON Lines | Tags, captions, text, every shape type | Yes | A `metadata.jsonl` file. Hugging Face can load it directly |
| Text spans (JSON Lines) | Spans in documents, document tags | Yes | A `.jsonl` file whose lines hold `text` and `spans`. Used by text projects. The words are written into the file, so the export stands alone |

Katib also finds a dataset that sits one folder down inside the folder you chose, such as a
`data.yaml` in a subfolder.

### Tags, captions and text

Use JSON Lines for image tags, captions and any text written inside a shape. Each line describes one
picture:

```json
{"file_name": "images/train/a.jpg", "width": 640, "height": 480, "split": "train",
 "tags": ["street"], "text": "A red bicycle by a wall.", "texts": ["A red bicycle by a wall."],
 "regions": [{"label": "sign", "type": "box", "geometry": {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}, "text": "STOP"}]}
```

- `text` is the first caption. `texts` lists every caption.
- `regions` holds the shapes. Their coordinates are fractions of the picture's width and height, so
  0.5 is the middle.
- If you include the pictures in the export, Hugging Face loads the folder with
  `load_dataset("imagefolder", data_dir=...)`. You can also import the same file back into Katib.

When a format cannot hold a shape, Katib converts it where that makes sense. For example, a polygon
becomes its bounding box in YOLO detection. Shapes that cannot be converted are skipped. The export
report lists every change, so nothing disappears without a note.

## Exporting

Choose **Export**. Pick a format, and choose which pictures to include: all of them, only the ones
marked done, or only the ones not yet done. You can include the picture files or leave them out.

Every export format is tested. The tests export a project that has one of each shape type, unpack the
zip, import it into an empty project, and check that the shapes came back.

### Splits in exports

If your pictures have splits, the export uses them and writes the `train`, `val` and `test` folders
your training code expects. Pictures without a split go into the training set. You can also make a new
split just for this export, or export without any split. See [Splits](#splits).

### Class order

YOLO identifies each class by its position in the list, not its name. If you change the order of your
classes, Katib warns you before the next export, because the numbers will change.

## Text documents

A project that uses **Text spans** holds documents instead of pictures. Everything else works the
same way: the same roles, the same queue of work, the same splits, and the same 30 days of undo.

### Adding documents

Choose **Add documents** and pick your files.

- A `.txt` or `.md` file becomes one document.
- A `.jsonl` file holds one document per line. Katib reads the words from `text`, and takes the
  document's name from `id` if the line has one.
- If a line already carries spans, in `spans` or `entities`, they come in as labels, and any class
  they name is created. Both shapes are read: `{"start": 0, "end": 5, "label": "product"}` and
  `[0, 5, "product"]`.
- A line can also carry `tags`, which label the whole document. That is what to use for sorting
  documents into categories.

The same words are only added once, however many times you add the file.

A document can be up to 400,000 characters, which is about 100 pages.

### Labelling words

See [Drawing and shortcuts](drawing.md#text-documents) for how to label spans.

### Exporting

Export with **Text spans (JSON Lines)**. Each line holds the document's words and its spans:

```json
{"id": "review-1", "text": "Katib runs on my laptop.", "split": "train",
 "tags": ["positive"], "spans": [{"start": 0, "end": 5, "label": "product", "text": "Katib"}]}
```

`start` is the first character and `end` the one just past the last, so `text[start:end]` is the
labelled words. Offsets count characters, so an accent or an emoji counts as one. The same file can
be imported again, and spans attach to the documents whose names match.

## Duplicates and dataset health

Open **Dataset health** for a report on tiny shapes, duplicate shapes, near-identical pictures,
pictures with no shapes, and classes with far fewer examples than the rest. See
[Classes and dataset health](classes.md).
