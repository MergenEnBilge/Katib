"""Click-to-select with a Segment Anything model.

SAM comes in two halves. The encoder looks at the whole picture once and produces an embedding,
which is the slow part. The decoder then turns that embedding plus a click into a mask, which is
fast enough to feel immediate. Katib keeps the embedding of the picture being worked on, so the
first click on an image costs a second or two and every click after it costs almost nothing.

Both halves are the user's own files. Katib never downloads a model. onnxruntime is an optional
extra, so it is imported only when a model is opened.
"""

from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from katib.ml.onnx import MlUnavailable, ModelError

#: File names Katib looks for in the models folder. Two halves of one model, so they are fixed:
#: pairing arbitrary uploads by name is a puzzle nobody should have to solve.
ENCODER_NAME = "sam-encoder.onnx"
DECODER_NAME = "sam-decoder.onnx"

#: What SAM's encoder expects: the longest side scaled to this, the rest padded with black.
ENCODER_SIDE = 1024

#: The longest side of the mask Katib asks for back. The decoder will happily return one the size
#: of the original photo, which is tens of megabytes for an outline nobody can see that closely.
MASK_SIDE = 512

#: How the SAM authors normalise a picture before the encoder sees it.
PIXEL_MEAN = (123.675, 116.28, 103.53)
PIXEL_STD = (58.395, 57.12, 57.375)

#: How many pictures' embeddings to keep. Each is about four megabytes.
CACHE_SIZE = 4


def is_installed(folder: Path) -> bool:
    """Whether both halves of a model are in the models folder."""
    return (folder / ENCODER_NAME).is_file() and (folder / DECODER_NAME).is_file()


@dataclass(frozen=True)
class Click:
    """A point on the picture, as a fraction of its width and height."""

    x: float
    y: float
    #: False for "not this": a click that pushes the outline back off something it swallowed.
    positive: bool = True


@dataclass
class Embedding:
    """What the encoder made of one picture, with the size it was scaled to."""

    values: Any
    width: int
    height: int


def _fit(width: int, height: int, side: int) -> tuple[int, int]:
    """The size of the picture with its longest side scaled to `side`."""
    scale = side / max(width, height)
    return max(1, round(width * scale)), max(1, round(height * scale))


class SamSegmenter:
    """A loaded pair of models. Building one reads both files, so keep it and reuse it."""

    def __init__(self, folder: Path) -> None:
        try:
            import onnxruntime as ort  # pyright: ignore[reportMissingImports]
        except ImportError as err:
            raise MlUnavailable(
                "Click to select needs an extra package. Install it with: uv sync --extra ml"
            ) from err
        self._folder = folder
        cpu = ["CPUExecutionProvider"]
        try:
            self._encoder = ort.InferenceSession(str(folder / ENCODER_NAME), providers=cpu)
            self._decoder = ort.InferenceSession(str(folder / DECODER_NAME), providers=cpu)
        except Exception as err:  # onnxruntime raises several unrelated types for a bad file
            raise ModelError(
                "Those files could not be loaded as a Segment Anything model. "
                "Katib needs the two ONNX files, the image encoder and the mask decoder."
            ) from err
        self._decoder_inputs = {i.name for i in self._decoder.get_inputs()}
        self._cache: OrderedDict[str, Embedding] = OrderedDict()

    def _encode(self, path: Path) -> Embedding:
        import numpy as np

        with Image.open(path) as source:
            picture = source.convert("RGB")
        width, height = _fit(picture.width, picture.height, ENCODER_SIDE)
        resized = picture.resize((width, height))
        pixels = np.asarray(resized, dtype=np.float32)
        pixels = (pixels - np.array(PIXEL_MEAN, dtype=np.float32)) / np.array(
            PIXEL_STD, dtype=np.float32
        )
        # The encoder wants a square. SAM pads the right and bottom with zeros, which after the
        # normalising above is the mean colour rather than black.
        canvas = np.zeros((ENCODER_SIDE, ENCODER_SIDE, 3), dtype=np.float32)
        canvas[:height, :width] = pixels
        tensor = canvas.transpose(2, 0, 1)[None]
        name = self._encoder.get_inputs()[0].name
        values: Any = self._encoder.run(None, {name: tensor})[0]
        return Embedding(values=values, width=width, height=height)

    def embedding(self, path: Path, key: str) -> Embedding:
        """The encoder's view of one picture, from the cache when it is there."""
        found = self._cache.get(key)
        if found is not None:
            self._cache.move_to_end(key)
            return found
        made = self._encode(path)
        self._cache[key] = made
        while len(self._cache) > CACHE_SIZE:
            self._cache.popitem(last=False)
        return made

    def outline(
        self, path: Path, key: str, clicks: list[Click]
    ) -> list[tuple[float, float]] | None:
        """The outline of whatever the clicks point at, as fractions of the picture."""
        import numpy as np

        from katib.core import mask as mask_module

        if not clicks:
            return None
        embedding = self.embedding(path, key)

        # Ask for the mask at a size worth drawing rather than at the size of the photograph. The
        # decoder scales its answer to whatever size it is told the picture is, so a smaller one
        # costs nothing and keeps the reply small.
        out_width, out_height = _fit(embedding.width, embedding.height, MASK_SIDE)
        scale = ENCODER_SIDE / max(out_width, out_height)

        points = [[c.x * out_width * scale, c.y * out_height * scale] for c in clicks]
        labels = [1.0 if c.positive else 0.0 for c in clicks]
        # Without a box to work from, SAM expects one padding point that means "nothing here".
        points.append([0.0, 0.0])
        labels.append(-1.0)

        feed: dict[str, Any] = {
            "image_embeddings": embedding.values,
            "point_coords": np.array([points], dtype=np.float32),
            "point_labels": np.array([labels], dtype=np.float32),
            "mask_input": np.zeros((1, 1, 256, 256), dtype=np.float32),
            "has_mask_input": np.zeros(1, dtype=np.float32),
            "orig_im_size": np.array([out_height, out_width], dtype=np.float32),
        }
        wanted = {name: value for name, value in feed.items() if name in self._decoder_inputs}
        try:
            outputs: Any = self._decoder.run(None, wanted)
        except Exception as err:
            raise ModelError("The mask decoder refused these clicks.") from err

        masks = outputs[0]
        scores = outputs[1] if len(outputs) > 1 else None
        best = int(np.argmax(scores[0])) if scores is not None and scores[0].size > 1 else 0
        grid = np.asarray(masks[0][best] if masks[0].ndim == 3 else masks[0])
        flat = (grid > 0).astype(np.uint8).reshape(-1).tolist()
        height, width = grid.shape
        return mask_module.polygon(flat, width, height)
