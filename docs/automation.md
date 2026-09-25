# REST API and Python client

Everything the interface does goes through a REST API, so you can script it.

## The API

The API lives under `/api/v1`. A running server describes itself at `/openapi.json`. Open that file in any OpenAPI viewer to browse every route and its fields.

Errors always have the same shape, so you can test for a code and show the message:

```json
{ "code": "project_name_taken", "message": "A project named “Street” already exists.", "details": {} }
```

Long jobs, such as importing a folder or exporting a dataset, return a job. Poll `GET /api/v1/jobs/{id}` until its status is `done` or `failed`.

### Tokens

With accounts off, no sign-in is needed. With accounts on, create an API token and send it in a header:

```bash
curl -H "Authorization: Bearer $KATIB_TOKEN" https://katib.example.com/api/v1/projects
```

Create a token by signing in and calling `POST /api/v1/auth/tokens` with a name. The token is shown once, and only its hash is stored. Revoke it with `DELETE /api/v1/auth/tokens/{id}`. A token can do what its owner can do.

### Saving shapes safely

Shapes are saved with `POST /api/v1/images/{id}/annotations:batch`. You choose the id of each new shape, so sending a batch again after a dropped connection is harmless: a create for an id that already exists succeeds without adding a second copy. Updates and deletes can carry `if_version`, and the answer for each operation says whether it succeeded, was refused, or conflicted with a newer edit.

## The Python client

```bash
pip install ./sdk
```

```python
from katib_client import Katib

katib = Katib("http://127.0.0.1:8420")  # add token="..." when accounts are on

project = katib.projects.create("Street scenes")
car = katib.classes.create(project.id, "car")

image = katib.images.upload(project.id, "photos/one.jpg")
katib.annotations.add_boxes(image.id, [(car.id, 0.2, 0.3, 0.4, 0.3)])  # class, x, y, w, h

katib.export(project.id, "yolo-detect", "exports/")  # saves a zip
```

Box values are fractions of the image, from 0 to 1, measured from the top left corner. The client covers projects, classes, images, annotations, folder connection, label import and export. Errors raise `KatibError` with a `code` and a `message`.

See the [client's own page](https://github.com/MergenEnBilge/Katib/tree/main/sdk) for the full list of calls.
