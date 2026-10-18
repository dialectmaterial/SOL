"""Invented multi-paragraph and cyclic book notes, with reciprocal links."""
from copy import deepcopy
import json
from uuid import UUID


def footnote_records(records, passage_id, *, depth=10):
    records = deepcopy(records)
    passage = next(row for row in records if row["id"] == passage_id)
    template = deepcopy(passage)
    template.pop("note_ids", None)
    notes, bodies = [], []
    for index in range(depth):
        note = deepcopy(template)
        note.update(id=str(UUID(int=1000 + index)), type="note", parent_id=passage_id,
                    order=len(records), label="12" if index == 0 else str(index + 6),
                    markdown=f"#### Note {index + 1}", plain_text=f"Note {index + 1}", backlinks=[],
                    attribution={"author": "Invented translator", "status": "editorial", "role": "footnote"})
        records.append(note)
        notes.append(note)
        body = deepcopy(note)
        body.pop("label"); body.pop("backlinks")
        body.update(id=str(UUID(int=2000 + index)), type="note_paragraph", parent_id=note["id"],
                    order=len(records), markdown=f"A *nested* thought {index + 1}.",
                    plain_text=f"A nested thought {index + 1}.")
        records.append(body)
        bodies.append(body)
    passage["note_ids"] = [notes[0]["id"]]
    notes[0]["backlinks"].append(passage_id)
    passage["markdown"] += f'<sup data-sol-note="{notes[0]["id"]}">[12](#{notes[0]["id"]})</sup>'
    for index, body in enumerate(bodies[:-1]):
        target = notes[index + 1]
        body["note_ids"] = [target["id"]]
        target["backlinks"].append(body["id"])
        body["markdown"] += f'<sup data-sol-note="{target["id"]}">[{target["label"]}](#{target["id"]})</sup>'
    # A genuine note-link cycle, independent of the acyclic parent hierarchy.
    bodies[1]["note_ids"].append(notes[0]["id"])
    notes[0]["backlinks"].append(bodies[1]["id"])
    bodies[0].update(markdown='α *first* thought' +
                     f'<sup data-sol-note="{notes[1]["id"]}">[7](#{notes[1]["id"]})</sup> é.',
                     plain_text="α first thought é.")
    second = deepcopy(bodies[0])
    second.pop("note_ids")
    second.update(id=str(UUID(int=3000)), order=len(records), markdown="A **second** body.\nAnother `line`.",
                  plain_text="A second body.\nAnother line.", transcription_status="needs_visual_review",
                  attribution={"author": "Another editor", "status": "editorial", "role": "footnote"})
    records.append(second)
    return records, [note["id"] for note in notes], [bodies[0]["id"], second["id"]]


def add_footnote_corpus(corpus, passage_id):
    """Reindex only an invented test corpus after adding canonical note records."""
    from sol.corpus import contract
    rows = [json.loads(line) for line in (corpus / "index.jsonl").read_text().splitlines()]
    rows, notes, bodies = footnote_records(rows, passage_id)
    generated = {"markdown", "plain_text", "document", "context", "content_sha256"}
    (corpus / "sample.md").write_text("\n".join(contract.render_record(
        {key: value for key, value in row.items() if key not in generated}, row["markdown"]) for row in rows),
        encoding="utf-8")
    contract.reindex(corpus)
    return notes, bodies
