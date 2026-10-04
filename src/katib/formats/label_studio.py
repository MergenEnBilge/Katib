"""Label Studio JSON: one object per task, holding the text and a list of results.

This is the format people bring with them when they move from Label Studio, and the one they take
back if they go on using it. A task looks like this::

    {"data": {"text": "Ada works at Katib."},
     "annotations": [{"result": [
       {"id": "a1", "from_name": "label", "to_name": "text", "type": "labels",
        "value": {"start": 0, "end": 3, "labels": ["person"]}},
       {"from_name": "rel", "to_name": "text", "type": "relation",
        "from_id": "a1", "to_id": "a2", "labels": ["works for"]}
     ]}]}

Spans, whole-document labels (`choices`) and relations all fit, so a project can go out and come
back whole. Offsets are characters, as Katib keeps them, so nothing is widened.
"""

import json
from pathlib import Path
from typing import Any

from katib.core.dataset import (
    DatasetView,
    ExportOptions,
    ExportReport,
    ImageLabels,
    Note,
    ParsedDataset,
    Shape,
)

FILE = "tasks.json"


def _tasks(path: Path) -> list[dict[str, Any]]:
    found = path if path.is_file() else None
    if found is None and path.is_dir():
        for name in (FILE, "project.json", "annotations.json", "export.json"):
            here = path / name
            if here.is_file():
                found = here
                break
        else:
            files = sorted(path.glob("*.json"))
            found = files[0] if files else None
    if found is None or found.suffix.lower() != ".json":
        return []
    try:
        parsed = json.loads(found.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return []
    rows = parsed if isinstance(parsed, list) else [parsed]
    return [dict(r) for r in rows if isinstance(r, dict)]  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]


def _text_of(task: dict[str, Any]) -> str | None:
    data = task.get("data")
    if isinstance(data, dict):
        for key in ("text", "content", "dialogue", "body"):
            value = data.get(key)  # pyright: ignore[reportUnknownMemberType]
            if isinstance(value, str):
                return value
    value = task.get("text")
    return value if isinstance(value, str) else None


def _results(task: dict[str, Any]) -> list[dict[str, Any]]:
    """Every result in the task, whichever of the three places it keeps them."""
    out: list[dict[str, Any]] = []
    for key in ("annotations", "completions"):
        raw = task.get(key)
        if not isinstance(raw, list):
            continue
        for entry in raw:  # pyright: ignore[reportUnknownVariableType]
            if isinstance(entry, dict):
                inner = entry.get("result")  # pyright: ignore[reportUnknownMemberType]
                if isinstance(inner, list):
                    out.extend(r for r in inner if isinstance(r, dict))  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
    predictions = task.get("result")
    if isinstance(predictions, list):
        out.extend(r for r in predictions if isinstance(r, dict))  # pyright: ignore[reportUnknownArgumentType, reportUnknownVariableType]
    return out


def _first_label(value: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        raw = value.get(key)
        if isinstance(raw, str):
            return raw
        if isinstance(raw, list) and raw and isinstance(raw[0], str):
            return str(raw[0])
    return None


class LabelStudio:
    id = "label-studio"
    label = "Label Studio (JSON, carries relations)"
    medium = "text"
    supports = frozenset({"span", "tag", "relation"})

    def detect(self, path: Path) -> bool:
        tasks = _tasks(path)
        return any(
            _text_of(task) is not None and ("annotations" in task or "completions" in task)
            for task in tasks
        )

    def read(self, path: Path, sizes: Any = None) -> ParsedDataset:
        del sizes
        names: list[str] = []
        documents: list[ImageLabels] = []
        notes: list[Note] = []
        for number, task in enumerate(_tasks(path), start=1):
            text = _text_of(task)
            if text is None:
                continue
            name = str(task.get("id") or f"task-{number}")
            shapes: list[Shape] = []
            seen: set[str] = set()
            links: list[tuple[str, str, str]] = []
            for result in _results(task):
                kind = str(result.get("type", ""))
                value = result.get("value")
                value = value if isinstance(value, dict) else {}
                if kind == "relation":
                    first = result.get("from_id")
                    second = result.get("to_id")
                    label = _first_label(result, "labels") or "related to"
                    if isinstance(first, str) and isinstance(second, str):
                        links.append((label, f"{name}-{first}", f"{name}-{second}"))
                    continue
                if kind == "choices" or "choices" in value:
                    for choice in value.get("choices", []) or []:  # pyright: ignore[reportUnknownVariableType]
                        if isinstance(choice, str):
                            if choice not in names:
                                names.append(choice)
                            shapes.append(Shape(choice, "tag", {}))
                    continue
                start, end = value.get("start"), value.get("end")  # pyright: ignore[reportUnknownMemberType]
                label = _first_label(value, "labels", "hypertextlabels", "label")
                if not isinstance(start, int) or not isinstance(end, int) or label is None:
                    continue
                if start < 0 or end > len(text) or end <= start:
                    notes.append(Note(name, f"A {label} span did not fit the words."))
                    continue
                if label not in names:
                    names.append(label)
                made = f"{name}-{result.get('id', len(shapes))}"
                seen.add(made)
                shapes.append(Shape(label, "span", {"start": start, "end": end}, id=made))
            for label, first, second in links:
                if first not in seen or second not in seen:
                    notes.append(Note(name, f"A {label} link pointed at nothing."))
                    continue
                if label not in names:
                    names.append(label)
                shapes.append(Shape(label, "relation", {"from_id": first, "to_id": second}))
            documents.append(ImageLabels(name, shapes, len(text), 1, text=text))
        return ParsedDataset(names, documents, notes)

    def write(self, view: DatasetView, dest: Path, opts: ExportOptions) -> ExportReport:
        del opts
        report = ExportReport()
        dest.mkdir(parents=True, exist_ok=True)
        tasks: list[dict[str, Any]] = []
        for item in view.images():
            text = item.text
            if text is None:
                report.notes.append(
                    Note(item.filename, "Only text documents go into a Label Studio export.")
                )
                continue
            results: list[dict[str, Any]] = []
            marks: dict[str, str] = {}
            for number, span in enumerate(item.spans(), start=1):
                mark = f"s{number}"
                if span.id:
                    marks[span.id] = mark
                start, end = int(span.geometry["start"]), int(span.geometry["end"])
                results.append(
                    {
                        "id": mark,
                        "from_name": "label",
                        "to_name": "text",
                        "type": "labels",
                        "value": {
                            "start": start,
                            "end": end,
                            "text": text[start:end],
                            "labels": [span.class_name],
                        },
                    }
                )
            for tag in item.tags():
                results.append(
                    {
                        "from_name": "choice",
                        "to_name": "text",
                        "type": "choices",
                        "value": {"choices": [tag]},
                    }
                )
            for link in item.relations():
                first = marks.get(str(link.geometry.get("from_id", "")))
                second = marks.get(str(link.geometry.get("to_id", "")))
                if first is None or second is None:
                    report.notes.append(
                        Note(item.filename, "A link joined a span that is not in this export.")
                    )
                    continue
                results.append(
                    {
                        "from_name": "relation",
                        "to_name": "text",
                        "type": "relation",
                        "from_id": first,
                        "to_id": second,
                        "direction": "right",
                        "labels": [link.class_name],
                    }
                )
            task: dict[str, Any] = {
                "id": item.filename,
                "data": {"text": text},
                "annotations": [{"result": results}],
            }
            if item.split:
                task["meta"] = {"split": item.split}
            tasks.append(task)
            report.images += 1
            report.shapes += len(results)
        (dest / FILE).write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
