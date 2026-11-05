#!/usr/bin/env python3
"""
Run from src/ (after apply_sql_patch.py):   python apply_sql_patch2.py
Fixes the self-correction loop repeating the same SQL when a column lives in another table:
  1. removes the contradictory correction rule "Use JOIN only when supported by the schema"
  2. when the validator says "Column 'x' could not be resolved", tells the model which table
     owns that column and which relationship to JOIN along (generic: read from the schema)
  3. adds one generic rule to the generation prompt about columns of other tables
Backups: *.bak2
"""
import pathlib, shutil, sys

CTRL = pathlib.Path("controllers/SQLController.py")
HINTS = pathlib.Path("stores/sql/SchemaHints.py")
TPL = pathlib.Path("stores/sql/templates/locales/en/sql.py")

for p in (CTRL, HINTS, TPL):
    if not p.exists():
        sys.exit(f"Missing {p}. Run from src/ and apply apply_sql_patch.py first.")

ctrl = CTRL.read_text(encoding="utf-8")
hints = HINTS.read_text(encoding="utf-8")
tpl = TPL.read_text(encoding="utf-8")

if "join_hint" in ctrl:
    sys.exit("Already patched.")

def once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        sys.exit(f"Patch point '{label}' found {n} times (expected 1). Nothing was changed.")
    return text.replace(old, new)

ctrl = once(ctrl,
    "from stores.sql.SchemaHints import add_schema_hints, dialect_notes",
    "from stores.sql.SchemaHints import add_schema_hints, dialect_notes, join_hint",
    "import")

ctrl = once(ctrl,
    "Do not invent relationships.\n\nUse JOIN only when supported by the schema.\n",
    "Do not invent columns or tables.\n\n"
    "Relationships listed in the schema (declared or inferred) are valid: JOIN along them.\n\n"
    "If a column you need is not in the tables used so far but exists in another table,\n"
    "JOIN that table using the listed relationships. Never repeat the previous SQL unchanged.\n",
    "correction-rules")

ctrl = once(ctrl,
    '        correction_prompt = f"""',
    '        error = join_hint(error, schema)\n\n        correction_prompt = f"""',
    "correction-hint")

tpl = once(tpl,
    '    "For top / highest / lowest / latest N questions use ORDER BY with LIMIT.",',
    '    "Every column you reference must belong to a table in FROM or JOIN. If a needed column "\n'
    '    "(for a calculation, filter, or output) is in another table, JOIN that table along the "\n'
    '    "listed relationships. If a measure is not a column, compute it from the numeric columns "\n'
    '    "of the related tables.",\n\n'
    '    "For top / highest / lowest / latest N questions use ORDER BY with LIMIT.",',
    "template-rule")

hints += '''

import re as _re


def join_hint(error, schema):
    """If the error says a column could not be resolved, say which table owns it
    and which relationships to JOIN along. Generic: uses only the schema."""
    text = str(error or "")
    match = _re.search(r"Column '([^']+)' could not be resolved", text)
    if not match:
        return error
    wanted = match.group(1).split(".")[-1].lower()
    owners = [
        table for table, info in schema.items()
        if any(str(c.get("name", "")).lower() == wanted for c in info.get("columns", []))
    ]
    if not owners:
        return error
    relations = [
        line
        for info in schema.values()
        for line in info.get("inferred_relationships", [])
        if any(owner in line for owner in owners)
    ]
    hint = (
        f"\\nHint: column '{match.group(1)}' does not exist in the table(s) used by the previous SQL. "
        f"It exists in: {', '.join(owners)}. JOIN that table"
    )
    if relations:
        hint += " using: " + "; ".join(relations)
    hint += ". Do not repeat the previous SQL unchanged."
    return text + hint
'''

for p, new in ((CTRL, ctrl), (HINTS, hints), (TPL, tpl)):
    shutil.copy(p, str(p) + ".bak2")
    p.write_text(new, encoding="utf-8")
print("Patched. Restart the server.")