"""Text document routes: adding documents to a project, and reading the words of one."""

import uuid
from typing import Annotated

from fastapi import APIRouter, File, UploadFile

from katib.api.deps import RunnerDep, SessionDep, StorageDep, UserDep, need
from katib.api.jobs import job_out
from katib.api.schemas import DocumentTextOut, JobOut
from katib.jobs.runner import Progress
from katib.services import documents, images, projects
from katib.services.errors import InvalidInput, NotFound

router = APIRouter(tags=["documents"])


@router.post("/projects/{project_id}/documents", response_model=JobOut, status_code=202)
def add_documents(
    project_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    session: SessionDep,
    user: UserDep,
    storage: StorageDep,
    runner: RunnerDep,
) -> JobOut:
    """Add documents from one uploaded file.

    A `.txt` or `.md` file is one document. A `.jsonl` file is one document per line, and any
    spans a line already carries come in with it, with their classes.
    """
    need(session, user, project_id, "manage")
    projects.get_project(session, project_id)
    name = file.filename or "documents.txt"
    data = file.file.read(storage.max_upload_bytes + 1)
    if len(data) > storage.max_upload_bytes:
        raise InvalidInput(f"A file can be up to {storage.max_upload_bytes // (1024 * 1024)} MB.")
    if not data:
        raise InvalidInput("That file is empty.")
    # Reading the words here, not in the job, so a file Katib cannot read is refused at once.
    text = documents.decode(name, data)
    factory = runner.session_factory

    def work(progress: Progress) -> dict[str, object]:
        with factory() as s:
            report = documents.import_file(s, project_id, name, text, storage)
        return {
            "added": report.added,
            "spans": report.spans,
            "classes_created": report.classes_created,
            "skipped": [{"name": k.name, "reason": k.reason} for k in report.skipped[:200]],
            "skipped_count": len(report.skipped),
        }

    job_id = runner.submit("import_documents", project_id, {"file": name}, work)
    job = runner.get(job_id)
    if job is None:
        raise NotFound("The document import could not be started.")
    return job_out(job)


@router.get("/images/{image_id}/text", response_model=DocumentTextOut)
def document_text(
    image_id: uuid.UUID, session: SessionDep, user: UserDep, storage: StorageDep
) -> DocumentTextOut:
    """The words of a document, for the workspace to show and label."""
    item = images.get_image(session, image_id)
    need(session, user, item.project_id, "view")
    text = documents.read_text(item, storage)
    return DocumentTextOut(filename=item.filename, text=text)
