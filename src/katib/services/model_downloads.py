"""Fetching a model Katib knows about, instead of asking someone to go and find their own file.

Every entry in CATALOG names a real file at a URL Katib does not control. Each one is pinned by a
sha256 computed from the exact bytes once, here, when it was added to this file -- if that file
ever changes at the source, the download is refused rather than silently installing something
nobody checked. This is the one place Katib reaches onto the network on its own; everything else
it does stays on the machine that runs it.
"""

import hashlib
import shutil
import tempfile
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from katib.ml import sam
from katib.services.errors import InvalidInput

Progress = Callable[[float], None]

#: Sent with every request. Some hosts refuse Python's default user agent outright.
USER_AGENT = "katib (+https://github.com/MergenEnBilge/Katib)"

#: Reject anything that answers with drastically more than it said it would, in case a redirect
#: or a compromised host ever pointed this at something else.
SIZE_SLACK = 1.05

#: Which catalog entry last installed the files in a models folder, so the interface can say
#: "this one is already installed" instead of just "something is".
MARKER_NAME = "sam-source.txt"


@dataclass(frozen=True)
class ModelSource:
    id: str
    label: str
    help: str
    url: str
    sha256: str
    bytes: int
    #: Names inside the downloaded zip, mapped to the filename Katib stores each one under.
    files: dict[str, str]


CATALOG: tuple[ModelSource, ...] = (
    ModelSource(
        id="mobile-sam",
        label="Segment Anything (MobileSAM, quantized)",
        help=(
            "The smallest click-to-select model, good enough for most photos and the fastest "
            "to load."
        ),
        url=(
            "https://huggingface.co/vietanhdev/segment-anything-onnx-models/"
            "resolve/main/mobile_sam_20230629_quant.zip"
        ),
        sha256="8a8ee531538541a55fa6fa7efebae121ef33e5c323b3998b48ea9383b37d90aa",
        bytes=10_971_233,
        files={
            "mobile_sam.encoder.quant.onnx": sam.ENCODER_NAME,
            "sam_vit_h_4b8939.decoder.quant.onnx": sam.DECODER_NAME,
        },
    ),
    ModelSource(
        id="sam-vit-b",
        label="Segment Anything (ViT-B, quantized)",
        help=(
            "Slower and about seven times the size, for masks with cleaner edges than MobileSAM's."
        ),
        url=(
            "https://huggingface.co/vietanhdev/segment-anything-onnx-models/"
            "resolve/main/sam_vit_b_01ec64_quant.zip"
        ),
        sha256="9d59db12affc009f71c9ddeab8fc833507510883e7f6bc4c0cc6c45e0d4f5862",
        bytes=75_377_417,
        files={
            "sam_vit_b_01ec64.encoder.quant.onnx": sam.ENCODER_NAME,
            "sam_vit_b_01ec64.decoder.quant.onnx": sam.DECODER_NAME,
        },
    ),
)

BY_ID = {m.id: m for m in CATALOG}


def find(model_id: str) -> ModelSource:
    found = BY_ID.get(model_id)
    if found is None:
        raise InvalidInput("That is not a model Katib knows how to download.")
    return found


def fetch(url: str, dest: Path, max_bytes: int, progress: Progress | None = None) -> None:
    """Stream a URL to `dest`. Refuses anything bigger than `max_bytes`."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            total = response.length or max_bytes
            written = 0
            with dest.open("wb") as out:
                while chunk := response.read(1024 * 1024):
                    written += len(chunk)
                    if written > max_bytes:
                        raise InvalidInput("That model is larger than expected. Stopped early.")
                    out.write(chunk)
                    if progress:
                        progress(min(written / total, 1.0))
    except OSError as err:
        raise InvalidInput(f"Could not reach {url}: {err}") from err


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def install_from_archive(source: ModelSource, archive: Path, folder: Path) -> None:
    """Verify a downloaded zip against `source` and unpack the files it names into `folder`."""
    if _sha256(archive) != source.sha256:
        raise InvalidInput(
            "That file did not match what Katib expected. It was not installed, in case the "
            "download was incomplete or the file at the source has changed."
        )
    folder.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        names = set(zf.namelist())
        missing = set(source.files) - names
        if missing:
            raise InvalidInput(f"That archive did not have the files Katib expected: {missing}.")
        for member, target_name in source.files.items():
            with zf.open(member) as src, (folder / target_name).open("wb") as out:
                shutil.copyfileobj(src, out)
    (folder / MARKER_NAME).write_text(source.id, encoding="utf-8")


def installed_id(folder: Path) -> str | None:
    marker = folder / MARKER_NAME
    if not marker.is_file():
        return None
    return marker.read_text(encoding="utf-8").strip() or None


def download_and_install(
    source: ModelSource, folder: Path, progress: Progress | None = None
) -> None:
    """Download `source` and install it into `folder`, cleaning up the download either way."""
    with tempfile.TemporaryDirectory() as scratch:
        archive = Path(scratch) / "download.zip"
        fetch(source.url, archive, int(source.bytes * SIZE_SLACK), progress)
        install_from_archive(source, archive, folder)
