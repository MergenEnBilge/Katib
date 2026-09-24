"""Print the OpenAPI spec to stdout. Used by `pnpm gen:api` so no server has to be running."""

import json
import sys
import tempfile

from katib.api.app import create_app
from katib.config import Settings

with tempfile.TemporaryDirectory() as tmp:
    app = create_app(Settings(storage={"data_dir": tmp}))
    json.dump(app.openapi(), sys.stdout)
