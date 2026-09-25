"""Running a YOLO detection model saved as ONNX.

The model is the user's own. Katib never downloads one. onnxruntime is an optional extra, so it
is imported only when a model is opened.
"""

import ast
from pathlib import Path
from typing import Any

from PIL import Image

from katib.core.detect import Detection, Layout, Letterbox, detect_boxes

DEFAULT_SIZE = 640
GRAY = (114, 114, 114)


class MlUnavailable(RuntimeError):
    """The optional machine learning packages are not installed."""


class ModelError(ValueError):
    """The file is not a model Katib can run. The message says why."""


def is_available() -> bool:
    try:
        import onnxruntime  # noqa: F401
    except ImportError:
        return False
    return True


def list_models(folder: Path) -> list[str]:
    """File names of the .onnx models in `folder`."""
    if not folder.is_dir():
        return []
    return sorted(p.name for p in folder.glob("*.onnx") if p.is_file())


def _class_names(metadata: dict[str, str]) -> list[str] | None:
    """Class names as exported by common YOLO tools, or None when the model carries none."""
    raw = metadata.get("names")
    if not raw:
        return None
    try:
        parsed: Any = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        return None
    if isinstance(parsed, dict):
        return [str(parsed[k]) for k in sorted(parsed, key=int)]
    if isinstance(parsed, list):
        return [str(n) for n in parsed]
    return None


class OnnxDetector:
    """A loaded model. Building one reads the file, so keep it while running many images."""

    def __init__(self, path: Path) -> None:
        try:
            import onnxruntime as ort
        except ImportError as err:
            raise MlUnavailable(
                "Model pre-labeling needs an extra package. Install it with: uv sync --extra ml"
            ) from err
        try:
            self._session = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
        except Exception as err:  # onnxruntime raises several unrelated types for a bad file
            raise ModelError(f"{path.name} could not be loaded as an ONNX model.") from err
        shape = self._session.get_inputs()[0].shape
        self._input = self._session.get_inputs()[0].name
        height, width = shape[2], shape[3]
        self.size = int(height) if isinstance(height, int) and height == width else DEFAULT_SIZE
        self.class_names = _class_names(self._session.get_modelmeta().custom_metadata_map)

    def detect(self, image_path: Path, threshold: float, iou: float = 0.45) -> list[Detection]:
        import numpy as np

        with Image.open(image_path) as source:
            picture = source.convert("RGB")
        fit = Letterbox.fit(picture.width, picture.height, self.size)
        resized = picture.resize(
            (max(1, round(picture.width * fit.scale)), max(1, round(picture.height * fit.scale)))
        )
        canvas = Image.new("RGB", (self.size, self.size), GRAY)
        canvas.paste(resized, (round(fit.pad_x), round(fit.pad_y)))
        tensor = np.asarray(canvas, dtype=np.float32).transpose(2, 0, 1)[None] / 255.0
        output: Any = self._session.run(None, {self._input: tensor})[0]
        if output.ndim != 3 or output.shape[0] != 1:
            raise ModelError("This model's output is not in a YOLO detection layout.")
        rows, layout = _arrange(output[0], len(self.class_names) if self.class_names else None)
        return detect_boxes(rows, layout, fit, threshold, iou)


def _arrange(grid: Any, class_count: int | None) -> tuple[list[list[float]], Layout]:
    """One row per candidate. YOLOv8 puts candidates in columns and YOLOv5 in rows.

    When the model names its classes, the number of values per candidate settles which layout it
    is. Otherwise the shorter side is taken to be the values.
    """
    rows, cols = grid.shape
    if class_count is not None and rows == 4 + class_count:
        return grid.T.tolist(), "v8"
    if class_count is not None and cols == 5 + class_count:
        return grid.tolist(), "v5"
    if rows < cols:
        return grid.T.tolist(), "v8"
    return grid.tolist(), "v5"
