"""List public tasks to seed in Firestore; private drafts are never included."""
import json
from pathlib import Path

from significance.records import load_record
from significance.render import is_published, task_id

root = Path(__file__).resolve().parents[2]
tasks = []
for path in sorted((root / 'records').glob('*.yaml')):
    record = load_record(path)
    if not is_published(record):
        continue
    for index, invitation in enumerate(record.get('open_invitations', [])):
        if invitation.get('status', 'open') not in {'open', 'taken'}:
            continue
        tid = task_id(invitation, index)
        tasks.append(dict(document_id=f"{record['record_id']}__{tid}",
                          record_id=record['record_id'], task_id=tid))
print(json.dumps(tasks, indent=2))
