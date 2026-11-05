#!/usr/bin/env python3
"""
Run from the project's src/ folder:   python apply_sql_patch.py
Makes the SQL generator tell the model the SQL dialect, adds per-column ranges,
distinct counts and inferred relationships (read from the database itself, so it
works for ANY uploaded file), and raises the output token limit.
Backups are written as *.bak. Safe to run twice (it refuses a second time).
"""
import base64, pathlib, shutil, sys

CTRL = pathlib.Path("controllers/SQLController.py")
HINTS = pathlib.Path("stores/sql/SchemaHints.py")
HINTS_B64 = "IiIiCkdlbmVyaWMgc2NoZW1hIGhpbnRzIGZvciB0aGUgU1FMIGdlbmVyYXRvci4gTm8gZmlsZS1zcGVjaWZpYyBrbm93bGVkZ2U6CmV2ZXJ5dGhpbmcgaXMgcmVhZCBmcm9tIHRoZSBkYXRhYmFzZSBpdHNlbGYgYXQgcnVuIHRpbWUuCgogIGRpYWxlY3Rfbm90ZXMoZGlhbGVjdCkgICAgICAgICAgICAtPiB0ZXh0IHRlbGxpbmcgdGhlIG1vZGVsIHdoaWNoIFNRTCBkaWFsZWN0IHRvIHdyaXRlCiAgYWRkX3NjaGVtYV9oaW50cyhtb2RlbCwgc2NoZW1hKSAgIC0+IGFkZHMgcGVyLWNvbHVtbiBzdGF0cyBhbmQgaW5mZXJyZWQgcmVsYXRpb25zaGlwcwoiIiIKCmltcG9ydCBsb2dnaW5nCmZyb20gdHlwaW5nIGltcG9ydCBBbnksIERpY3QsIExpc3QKCmxvZ2dlciA9IGxvZ2dpbmcuZ2V0TG9nZ2VyKCJ1dmljb3JuLmVycm9yIikKCl9ESUFMRUNUX05PVEVTID0gewogICAgInNxbGl0ZSI6IFsKICAgICAgICAiU1FMIGRpYWxlY3Q6IFNRTGl0ZS4iLAogICAgICAgICJObyBJTElLRSwgRVhUUkFDVCwgREFURV9UUlVOQywgREFURURJRkYsIE5PVygpLCBNRURJQU4sIG9yIEZVTEwgT1VURVIgSk9JTi4iLAogICAgICAgICJEQVRFIGFuZCBUSU1FU1RBTVAgY29sdW1ucyBhcmUgc3RvcmVkIGFzIElTTyB0ZXh0ICgnWVlZWS1NTS1ERCcgb3IgJ1lZWVktTU0tREQgSEg6TU06U1MnKTogIgogICAgICAgICJjb21wYXJlIHRoZW0gYXMgdGV4dCBhbmQgdXNlIHN0cmZ0aW1lKCclWScsIGNvbCksIHN0cmZ0aW1lKCclbScsIGNvbCksIHN0cmZ0aW1lKCclWS0lbScsIGNvbCkgIgogICAgICAgICJmb3IgeWVhciAvIG1vbnRoIGdyb3VwaW5nLiIsCiAgICAgICAgIlVzZSBST1VORCh4LCAyKSBmb3IgZGVjaW1hbHM7IHdpbmRvdyBmdW5jdGlvbnMgKFJPV19OVU1CRVIsIFJBTkssIFNVTSBPVkVSKSBhcmUgc3VwcG9ydGVkLiIsCiAgICBdLAogICAgInBvc3RncmVzcWwiOiBbCiAgICAgICAgIlNRTCBkaWFsZWN0OiBQb3N0Z3JlU1FMLiIsCiAgICAgICAgIlVzZSBFWFRSQUNUKFlFQVIgRlJPTSBjb2wpIG9yIERBVEVfVFJVTkMoJ21vbnRoJywgY29sKSBmb3IgZGF0ZSBwYXJ0czsgSUxJS0UgaXMgYWxsb3dlZC4iLAogICAgXSwKfQoKCmRlZiBkaWFsZWN0X25vdGVzKGRpYWxlY3Q6IHN0cikgLT4gc3RyOgogICAgbGluZXMgPSBfRElBTEVDVF9OT1RFUy5nZXQoKGRpYWxlY3Qgb3IgIiIpLmxvd2VyKCkpCiAgICBpZiBub3QgbGluZXM6CiAgICAgICAgbGluZXMgPSBbZiJTUUwgZGlhbGVjdDoge2RpYWxlY3Qgb3IgJ3Vua25vd24nfS4gVXNlIHN0YW5kYXJkIFNRTC4iXQogICAgcmV0dXJuICIjIyBTUUwgRGlhbGVjdFxuIiArICJcbiIuam9pbihsaW5lcykKCgpkZWYgX3EoaWRlbnRpZmllcjogc3RyKSAtPiBzdHI6CiAgICByZXR1cm4gJyInICsgc3RyKGlkZW50aWZpZXIpLnJlcGxhY2UoJyInLCAnIiInKSArICciJwoKCmRlZiBfdHlwZShjb2x1bW46IERpY3Rbc3RyLCBBbnldKSAtPiBzdHI6CiAgICByZXR1cm4gc3RyKGNvbHVtbi5nZXQoInR5cGUiLCAiIikpLnVwcGVyKCkKCgphc3luYyBkZWYgX3NjYWxhcl9yb3cobW9kZWwsIHF1ZXJ5OiBzdHIpIC0+IERpY3Rbc3RyLCBBbnldOgogICAgcmVzdWx0ID0gYXdhaXQgbW9kZWwuZXhlY3V0ZShxdWVyeT1xdWVyeSkKICAgIHJvd3MgPSByZXN1bHQuZ2V0KCJyb3dzIiwgW10pCiAgICByZXR1cm4gcm93c1swXSBpZiByb3dzIGVsc2Uge30KCgphc3luYyBkZWYgYWRkX3NjaGVtYV9oaW50cygKICAgIG1vZGVsLAogICAgc2NoZW1hOiBEaWN0W3N0ciwgQW55XSwKICAgIG1heF9saXN0ZWRfdmFsdWVzOiBpbnQgPSAyMCwKKSAtPiBEaWN0W3N0ciwgQW55XToKICAgICIiIgogICAgRm9yIGV2ZXJ5IGNvbHVtbiBhZGRzIGNvbHVtblsic3RhdHMiXToKICAgICAgLSBudW1lcmljICAgICAgICAgIC0+ICJyYW5nZTogbWluIHRvIG1heCIKICAgICAgLSBkYXRlIC8gdGltZXN0YW1wIC0+ICJyYW5nZTogbWluIHRvIG1heCIKICAgICAgLSB0ZXh0ICAgICAgICAgICAgIC0+ICJhbGwgTiB2YWx1ZXMgbGlzdGVkIiBpcyBoYW5kbGVkIGJ5IHRoZSBleGlzdGluZyBzYW1wbGVzOwogICAgICAgICAgICAgICAgICAgICAgICAgICAgaGVyZSB3ZSBvbmx5IGFkZCB0aGUgZGlzdGluY3QgY291bnQgc28gdGhlIG1vZGVsIGtub3dzCiAgICAgICAgICAgICAgICAgICAgICAgICAgICB3aGV0aGVyIHRoZSBzYW1wbGUgbGlzdCBpcyBjb21wbGV0ZSBvciBqdXN0IGV4YW1wbGVzLgogICAgRm9yIGV2ZXJ5IHRhYmxlIGFkZHMgdGFibGVfaW5mb1siaW5mZXJyZWRfcmVsYXRpb25zaGlwcyJdIChsaXN0IG9mIHRleHQgbGluZXMpOgogICAgICBhIGNvbHVtbiB3aXRoIHRoZSBzYW1lIG5hbWUgaW4gYW5vdGhlciB0YWJsZSB3aGVyZSB0aGF0IGNvbHVtbiBpcyB1bmlxdWUKICAgICAgKGEga2V5KSBpcyB0cmVhdGVkIGFzIGEgcmVsYXRpb25zaGlwIGNoaWxkIC0+IHBhcmVudC4KICAgIE5ldmVyIHJhaXNlczogYSBmYWlsdXJlIG9ubHkgbWVhbnMgZmV3ZXIgaGludHMuCiAgICAiIiIKCiAgICAjIC0tLS0tLS0tLS0gY29sdW1uIHN0YXRzIC0tLS0tLS0tLS0KICAgIGZvciB0YWJsZV9uYW1lLCB0YWJsZV9pbmZvIGluIHNjaGVtYS5pdGVtcygpOgogICAgICAgIGZvciBjb2x1bW4gaW4gdGFibGVfaW5mby5nZXQoImNvbHVtbnMiLCBbXSk6CiAgICAgICAgICAgIG5hbWUgPSBjb2x1bW5bIm5hbWUiXQogICAgICAgICAgICBjdHlwZSA9IF90eXBlKGNvbHVtbikKICAgICAgICAgICAgdHEsIGNxID0gX3EodGFibGVfbmFtZSksIF9xKG5hbWUpCiAgICAgICAgICAgIHRyeToKICAgICAgICAgICAgICAgIGlmIGFueSh0IGluIGN0eXBlIGZvciB0IGluICgiSU5UIiwgIkZMT0FUIiwgIlJFQUwiLCAiTlVNRVJJQyIsICJERUNJTUFMIiwgIkRPVUJMRSIsICJEQVRFIiwgIlRJTUUiKSk6CiAgICAgICAgICAgICAgICAgICAgcm93ID0gYXdhaXQgX3NjYWxhcl9yb3coCiAgICAgICAgICAgICAgICAgICAgICAgIG1vZGVsLAogICAgICAgICAgICAgICAgICAgICAgICBmIlNFTEVDVCBNSU4oe2NxfSkgQVMgbG8sIE1BWCh7Y3F9KSBBUyBoaSBGUk9NIHt0cX0iLAogICAgICAgICAgICAgICAgICAgICkKICAgICAgICAgICAgICAgICAgICBsbywgaGkgPSByb3cuZ2V0KCJsbyIpLCByb3cuZ2V0KCJoaSIpCiAgICAgICAgICAgICAgICAgICAgaWYgbG8gaXMgbm90IE5vbmUgYW5kIGhpIGlzIG5vdCBOb25lOgogICAgICAgICAgICAgICAgICAgICAgICBjb2x1bW5bInN0YXRzIl0gPSBmInJhbmdlOiB7bG99IHRvIHtoaX0iCiAgICAgICAgICAgICAgICBlbGlmIGFueSh0IGluIGN0eXBlIGZvciB0IGluICgiVEVYVCIsICJWQVJDSEFSIiwgIkNIQVIiLCAiU1RSSU5HIikpOgogICAgICAgICAgICAgICAgICAgIHJvdyA9IGF3YWl0IF9zY2FsYXJfcm93KAogICAgICAgICAgICAgICAgICAgICAgICBtb2RlbCwKICAgICAgICAgICAgICAgICAgICAgICAgZiJTRUxFQ1QgQ09VTlQoRElTVElOQ1Qge2NxfSkgQVMgbiBGUk9NIHt0cX0iLAogICAgICAgICAgICAgICAgICAgICkKICAgICAgICAgICAgICAgICAgICBuID0gcm93LmdldCgibiIpCiAgICAgICAgICAgICAgICAgICAgaWYgbiBpcyBub3QgTm9uZToKICAgICAgICAgICAgICAgICAgICAgICAgc2FtcGxlcyA9IGNvbHVtbi5nZXQoInNhbXBsZV92YWx1ZXMiKSBvciBbXQogICAgICAgICAgICAgICAgICAgICAgICBpZiBzYW1wbGVzIGFuZCBpbnQobikgPD0gbWF4X2xpc3RlZF92YWx1ZXMgYW5kIGxlbihzYW1wbGVzKSA+PSBpbnQobik6CiAgICAgICAgICAgICAgICAgICAgICAgICAgICBjb2x1bW5bInN0YXRzIl0gPSBmIntufSBkaXN0aW5jdCB2YWx1ZXMgKGFsbCBsaXN0ZWQpIgogICAgICAgICAgICAgICAgICAgICAgICBlbHNlOgogICAgICAgICAgICAgICAgICAgICAgICAgICAgY29sdW1uWyJzdGF0cyJdID0gZiJ7bn0gZGlzdGluY3QgdmFsdWVzICh0aGUgZXhhbXBsZXMgYXJlIG9ubHkgYSBzYW1wbGUpIgogICAgICAgICAgICAgICAgICAgICAgICAgICAgaWYgaW50KG4pID4gbWF4X2xpc3RlZF92YWx1ZXM6CiAgICAgICAgICAgICAgICAgICAgICAgICAgICAgICAgY29sdW1uWyJzYW1wbGVfdmFsdWVzIl0gPSBzYW1wbGVzWzozXSAgIyBhIGxvbmcgcGFydGlhbCBsaXN0IHdvdWxkIG1pc2xlYWQKICAgICAgICAgICAgZXhjZXB0IEV4Y2VwdGlvbiBhcyBleGM6CiAgICAgICAgICAgICAgICBsb2dnZXIud2FybmluZygiW1NRTCBERUJVR10gQ09MVU1OIFNUQVRTIEZBSUxFRCB8ICVzLiVzIHwgJXMiLCB0YWJsZV9uYW1lLCBuYW1lLCBleGMpCgogICAgIyAtLS0tLS0tLS0tIGluZmVycmVkIHJlbGF0aW9uc2hpcHMgKG9ubHkgd2hlbiB0aGUgc2NoZW1hIGRlY2xhcmVzIG5vbmUpIC0tLS0tLS0tLS0KICAgIHRyeToKICAgICAgICB1bmlxdWVfY2FjaGU6IERpY3RbdHVwbGUsIGJvb2xdID0ge30KCiAgICAgICAgYXN5bmMgZGVmIGlzX3VuaXF1ZSh0YWJsZTogc3RyLCBjb2w6IHN0cikgLT4gYm9vbDoKICAgICAgICAgICAga2V5ID0gKHRhYmxlLCBjb2wpCiAgICAgICAgICAgIGlmIGtleSBub3QgaW4gdW5pcXVlX2NhY2hlOgogICAgICAgICAgICAgICAgcm93ID0gYXdhaXQgX3NjYWxhcl9yb3coCiAgICAgICAgICAgICAgICAgICAgbW9kZWwsCiAgICAgICAgICAgICAgICAgICAgZiJTRUxFQ1QgQ09VTlQoKikgQVMgdG90YWwsIENPVU5UKERJU1RJTkNUIHtfcShjb2wpfSkgQVMgZCwgIgogICAgICAgICAgICAgICAgICAgIGYiQ09VTlQoe19xKGNvbCl9KSBBUyBubiBGUk9NIHtfcSh0YWJsZSl9IiwKICAgICAgICAgICAgICAgICkKICAgICAgICAgICAgICAgIHRvdGFsLCBkLCBubiA9IHJvdy5nZXQoInRvdGFsIiksIHJvdy5nZXQoImQiKSwgcm93LmdldCgibm4iKQogICAgICAgICAgICAgICAgdW5pcXVlX2NhY2hlW2tleV0gPSBib29sKHRvdGFsKSBhbmQgdG90YWwgPT0gbm4gPT0gZAogICAgICAgICAgICByZXR1cm4gdW5pcXVlX2NhY2hlW2tleV0KCiAgICAgICAgbmFtZXMgPSB7dDoge2NbIm5hbWUiXS5sb3dlcigpOiBjWyJuYW1lIl0gZm9yIGMgaW4gaW5mby5nZXQoImNvbHVtbnMiLCBbXSl9IGZvciB0LCBpbmZvIGluIHNjaGVtYS5pdGVtcygpfQoKICAgICAgICBmb3IgY2hpbGQsIGluZm8gaW4gc2NoZW1hLml0ZW1zKCk6CiAgICAgICAgICAgIGlmIGluZm8uZ2V0KCJmb3JlaWduX2tleXMiKToKICAgICAgICAgICAgICAgIGNvbnRpbnVlCiAgICAgICAgICAgIGxpbmVzOiBMaXN0W3N0cl0gPSBbXQogICAgICAgICAgICBmb3IgY29sX2xvd2VyLCBjb2wgaW4gbmFtZXNbY2hpbGRdLml0ZW1zKCk6CiAgICAgICAgICAgICAgICBmb3IgcGFyZW50IGluIHNjaGVtYToKICAgICAgICAgICAgICAgICAgICBpZiBwYXJlbnQgPT0gY2hpbGQgb3IgY29sX2xvd2VyIG5vdCBpbiBuYW1lc1twYXJlbnRdOgogICAgICAgICAgICAgICAgICAgICAgICBjb250aW51ZQogICAgICAgICAgICAgICAgICAgIHBhcmVudF9jb2wgPSBuYW1lc1twYXJlbnRdW2NvbF9sb3dlcl0KICAgICAgICAgICAgICAgICAgICAjIHBhcmVudCBzaWRlIG11c3QgYmUgYSBrZXksIGNoaWxkIHNpZGUgbXVzdCBub3QgYmUgdGhlIGtleSBvZiBpdHMgb3duIHRhYmxlCiAgICAgICAgICAgICAgICAgICAgaWYgYXdhaXQgaXNfdW5pcXVlKHBhcmVudCwgcGFyZW50X2NvbCkgYW5kIG5vdCBhd2FpdCBpc191bmlxdWUoY2hpbGQsIGNvbCk6CiAgICAgICAgICAgICAgICAgICAgICAgIGxpbmVzLmFwcGVuZChmIntjaGlsZH0ue2NvbH0gLT4ge3BhcmVudH0ue3BhcmVudF9jb2x9IikKICAgICAgICAgICAgaWYgbGluZXM6CiAgICAgICAgICAgICAgICBpbmZvWyJpbmZlcnJlZF9yZWxhdGlvbnNoaXBzIl0gPSBsaW5lcwogICAgZXhjZXB0IEV4Y2VwdGlvbiBhcyBleGM6CiAgICAgICAgbG9nZ2VyLndhcm5pbmcoIltTUUwgREVCVUddIFJFTEFUSU9OU0hJUCBJTkZFUkVOQ0UgRkFJTEVEIHwgJXMiLCBleGMpCgogICAgcmV0dXJuIHNjaGVtYQo="

if not CTRL.exists() or not HINTS.parent.exists():
    sys.exit("Run this from the src/ folder (controllers/ and stores/sql/ must exist).")

src = CTRL.read_text(encoding="utf-8")
if "add_schema_hints" in src:
    sys.exit("Already patched.")

def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        sys.exit(f"Patch point '{label}' found {n} times (expected 1). Nothing was changed.")
    return text.replace(old, new)

out = src

out = replace_once(
    out, "class SQLController:\n",
    "from stores.sql.SchemaHints import add_schema_hints, dialect_notes\n\n\nclass SQLController:\n",
    "import")

out = replace_once(
    out,
    "            return enriched_schema\n\n        finally:",
    "            await add_schema_hints(model, enriched_schema)\n\n"
    "            for _table_info in enriched_schema.values():\n"
    "                _table_info[\"dialect\"] = provider\n\n"
    "            return enriched_schema\n\n        finally:",
    "enrich")

out = replace_once(
    out,
    "        schema_parts: List[str] = []\n",
    "        schema_parts: List[str] = []\n\n"
    "        _first_table = next(iter(schema.values()), None) or {}\n\n"
    "        if _first_table.get(\"dialect\"):\n"
    "            schema_parts.append(dialect_notes(_first_table[\"dialect\"]))\n"
    "            schema_parts.append(\"\")\n"
    "            schema_parts.append(\"## Tables\")\n",
    "format-top")

out = replace_once(
    out,
    "                schema_parts.append(\n                    column_line\n                )\n",
    "                if column.get(\"stats\"):\n"
    "                    column_line += f\" | {column['stats']}\"\n\n"
    "                schema_parts.append(\n                    column_line\n                )\n",
    "format-stats")

out = replace_once(
    out,
    "            schema_parts.append(\"\")\n\n        return \"\\n\".join(",
    "            _relations = table_info.get(\"inferred_relationships\", [])\n\n"
    "            if _relations:\n"
    "                schema_parts.append(\"Relationships (inferred from matching key columns):\")\n"
    "                for _relation in _relations:\n"
    "                    schema_parts.append(f\"- {_relation}\")\n\n"
    "            schema_parts.append(\"\")\n\n        return \"\\n\".join(",
    "format-relations")

if out.count("max_output_tokens=256") != 2:
    sys.exit("Unexpected number of max_output_tokens=256 occurrences.")
out = out.replace("max_output_tokens=256", "max_output_tokens=512")

shutil.copy(CTRL, str(CTRL) + ".bak")
HINTS.write_bytes(base64.b64decode(HINTS_B64))
CTRL.write_text(out, encoding="utf-8")
print("Patched:", CTRL, "and created", HINTS, "(backup:", str(CTRL) + ".bak)")
print("Restart the server so the schema cache is rebuilt.")