# katib-client

A small Python client for a [Katib](../README.md) annotation server. Use it to script the things you would otherwise click through: creating projects, sending images, adding labels from your own code, and exporting a finished dataset.

```bash
pip install ./sdk
```

## A first script

```python
from katib_client import Katib

katib = Katib("http://127.0.0.1:8420")  # add token="..." when accounts are on

project = katib.projects.create("Street scenes")
car = katib.classes.create(project.id, "car")

image = katib.images.upload(project.id, "photos/one.jpg")
katib.annotations.add_boxes(image.id, [(car.id, 0.2, 0.3, 0.4, 0.3)])  # class, x, y, w, h

katib.export(project.id, "yolo-detect", "exports/")  # saves a zip
```

Box values are fractions of the image, from 0 to 1, measured from the top left corner.

## Accounts

When a server has accounts turned on, create an API token in Katib and pass it in:

```python
katib = Katib("https://katib.example.com", token="...")
```

## What is in it

| Call | What it does |
|------|--------------|
| `katib.projects.list()`, `.get(id)`, `.create(name, annotation_types=None)` | Projects |
| `katib.classes.list(project_id)`, `.create(project_id, name, color=None)` | Classes |
| `katib.images.list(project_id)` | Every image, a page at a time |
| `katib.images.upload(project_id, path)` | Send an image from this computer |
| `katib.images.connect_folder(project_id, folder)` | Read a folder on the server's computer, where it is |
| `katib.annotations.list(image_id)`, `.add_boxes(...)`, `.batch(...)` | Shapes on an image |
| `katib.import_labels(project_id, path, format=None)` | Add labels from a dataset on the server's computer |
| `katib.export(project_id, format, destination, ...)` | Export and download a zip |

Errors from the server raise `KatibError`, with a `code` you can test for and a `message` you can show.
