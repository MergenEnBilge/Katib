"""A small client for a Katib server.

from katib_client import Katib

katib = Katib("http://127.0.0.1:8420")
project = katib.projects.create("Street scenes")
car = katib.classes.create(project.id, "car")
katib.images.upload(project.id, "photos/one.jpg")
"""

from katib_client.client import (
    Annotation,
    ClassInfo,
    ImageInfo,
    Katib,
    KatibError,
    Project,
)

__all__ = ["Annotation", "ClassInfo", "ImageInfo", "Katib", "KatibError", "Project"]
