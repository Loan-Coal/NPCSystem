# Interface Contract — common

**Layer:** config  
**Status:** ✅ Done (session 3)

---

## json_utils.py

**Purpose:** Shared JSON parse/serialize helpers with safe fallbacks for untrusted inputs.  
**Does NOT:** enforce domain schema constraints.  
**Dependencies:** None.

### Public API

| Function | Signature | Description |
|----------|-----------|-------------|
| `parse_json_object` | `(value: object) -> dict[str, Any]` | Returns dict from native dict or JSON string; `{}` on invalid input. |
| `parse_json_list` | `(value: object) -> list[Any]` | Returns list from native list or JSON string; `[]` on invalid input. |
| `dump_json` | `(value: object) -> str` | Serializes any JSON-serializable value to a JSON string. |

### Error behaviour

- Parse helpers swallow `ValueError` from `json.loads` and return the fallback (`{}` / `[]`).  
- Wrong root type (e.g. list where dict expected) also returns the fallback — no exception raised.  
- `dump_json` propagates `TypeError` from `json.dumps` unmodified (caller's responsibility).

---

## yaml_utils.py

**Purpose:** Shared YAML loading helpers for config files that must have a mapping root.  
**Does NOT:** validate domain-specific schema contracts.  
**Dependencies:** None.

### Public API

| Function | Signature | Description |
|----------|-----------|-------------|
| `load_yaml_mapping` | `(path: Path, root_error_message: str) -> dict[str, Any]` | Reads YAML from disk and asserts a dict root. |

### Error behaviour

- Raises `ValueError(root_error_message)` when the YAML root is not a `dict`.  
- Propagates `FileNotFoundError` from `Path.read_text` when the file does not exist.
