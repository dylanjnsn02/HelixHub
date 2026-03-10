from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Union

from fastmcp import FastMCP
from tinydb import Query, TinyDB
from tinydb.table import Document
from toon import encode


mcp = FastMCP("tinydb-mcp")


JsonValue = Union[None, bool, int, float, str, List[Any], Dict[str, Any]]


def _open_db(db_path: str) -> TinyDB:
    return TinyDB(db_path)


def _get_table(db: TinyDB, table_name: Optional[str] = None):
    if table_name and table_name != "_default":
        return db.table(table_name)
    return db


def _normalize_doc(doc: Any) -> Any:
    if isinstance(doc, Document):
        data = dict(doc)
        data["doc_id"] = doc.doc_id
        return data
    if isinstance(doc, list):
        return [_normalize_doc(item) for item in doc]
    if isinstance(doc, dict):
        return {k: _normalize_doc(v) for k, v in doc.items()}
    return doc


def _to_toon_string(value: Any) -> str:
    normalized = _normalize_doc(value)
    return encode(normalized)


def _ensure_list(value: Any, field_name: str) -> List[Any]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    return value


def _build_query(spec: Dict[str, Any]):
    if not isinstance(spec, dict):
        raise ValueError("query spec must be an object")

    op = spec.get("op")
    q = Query()

    if op in {"and", "or"}:
        conditions = _ensure_list(spec.get("conditions"), "conditions")
        if not conditions:
            raise ValueError(f"{op} requires non-empty conditions")
        built = [_build_query(cond) for cond in conditions]
        expr = built[0]
        for item in built[1:]:
            expr = expr & item if op == "and" else expr | item
        return expr

    if op == "not":
        condition = spec.get("condition")
        if not isinstance(condition, dict):
            raise ValueError("not requires a condition object")
        return ~_build_query(condition)

    if op == "fragment":
        value = spec.get("value")
        if not isinstance(value, dict):
            raise ValueError("fragment requires an object value")
        return q.fragment(value)

    field = spec.get("field")
    if op != "fragment" and not field:
        raise ValueError(f"{op} requires field")

    field_query = q[field]

    if op == "eq":
        return field_query == spec.get("value")
    if op == "ne":
        return field_query != spec.get("value")
    if op == "lt":
        return field_query < spec.get("value")
    if op == "lte":
        return field_query <= spec.get("value")
    if op == "gt":
        return field_query > spec.get("value")
    if op == "gte":
        return field_query >= spec.get("value")
    if op == "exists":
        return field_query.exists()
    if op == "matches":
        pattern = spec.get("value")
        if not isinstance(pattern, str):
            raise ValueError("matches requires a string regex pattern")
        return field_query.matches(pattern)
    if op == "search":
        pattern = spec.get("value")
        if not isinstance(pattern, str):
            raise ValueError("search requires a string regex pattern")
        return field_query.search(pattern)
    if op == "one_of":
        values = _ensure_list(spec.get("value"), "value")
        return field_query.one_of(values)
    if op == "any":
        values = _ensure_list(spec.get("value"), "value")
        return field_query.any(values)
    if op == "all":
        values = _ensure_list(spec.get("value"), "value")
        return field_query.all(values)

    raise ValueError(f"Unsupported query op: {op}")


def _python_type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int) and not isinstance(value, bool):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "str"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "dict"
    return type(value).__name__


def _flatten_schema_info(
    obj: Any,
    prefix: str,
    paths: Dict[str, Counter],
    examples: Dict[str, Any],
):
    type_name = _python_type_name(obj)
    key = prefix or "$root"
    paths[key][type_name] += 1

    if key not in examples:
        examples[key] = obj

    if isinstance(obj, dict):
        for k, v in obj.items():
            child = f"{prefix}.{k}" if prefix else k
            _flatten_schema_info(v, child, paths, examples)
    elif isinstance(obj, list):
        for item in obj:
            child = f"{prefix}[]" if prefix else "[]"
            _flatten_schema_info(item, child, paths, examples)


@mcp.tool
def ping() -> Dict[str, str]:
    return {"status": "ok", "server": "tinydb-mcp"}


@mcp.tool
def list_tables(db_path: str) -> Dict[str, Any]:
    db = _open_db(db_path)
    try:
        return {"tables": sorted(list(db.tables()))}
    finally:
        db.close()


@mcp.tool
def create_table(db_path: str, table_name: str) -> Dict[str, Any]:
    db = _open_db(db_path)
    try:
        db.table(table_name)
        return {"created_or_opened": table_name, "tables": sorted(list(db.tables()))}
    finally:
        db.close()


@mcp.tool
def drop_table(db_path: str, table_name: str) -> Dict[str, Any]:
    db = _open_db(db_path)
    try:
        db.drop_table(table_name)
        return {"dropped": table_name, "tables": sorted(list(db.tables()))}
    finally:
        db.close()


@mcp.tool
def drop_tables(db_path: str) -> Dict[str, Any]:
    db = _open_db(db_path)
    try:
        db.drop_tables()
        return {"dropped_all_tables": True, "tables": sorted(list(db.tables()))}
    finally:
        db.close()


@mcp.tool
def insert_document(
    db_path: str,
    document: Dict[str, Any],
    table_name: Optional[str] = None,
) -> Dict[str, Any]:
    db = _open_db(db_path)
    try:
        table = _get_table(db, table_name)
        doc_id = table.insert(document)
        return {"doc_id": doc_id}
    finally:
        db.close()


@mcp.tool
def insert_documents(
    db_path: str,
    documents: List[Dict[str, Any]],
    table_name: Optional[str] = None,
) -> Dict[str, Any]:
    db = _open_db(db_path)
    try:
        table = _get_table(db, table_name)
        doc_ids = table.insert_multiple(documents)
        return {"doc_ids": doc_ids, "count": len(doc_ids)}
    finally:
        db.close()


@mcp.tool
def all_documents(
    db_path: str,
    table_name: Optional[str] = None,
) -> Dict[str, Any]:
    db = _open_db(db_path)
    try:
        table = _get_table(db, table_name)
        docs = table.all()
        return {
            "documents_toon": _to_toon_string(docs),
            "count": len(docs),
        }
    finally:
        db.close()


@mcp.tool
def get_document(
    db_path: str,
    table_name: Optional[str] = None,
    doc_id: Optional[int] = None,
    query: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if doc_id is None and query is None:
        raise ValueError("Provide either doc_id or query")

    db = _open_db(db_path)
    try:
        table = _get_table(db, table_name)
        if doc_id is not None:
            doc = table.get(doc_id=doc_id)
        else:
            doc = table.get(_build_query(query))
        return {
            "document_toon": _to_toon_string(doc) if doc is not None else "",
            "found": doc is not None,
        }
    finally:
        db.close()


@mcp.tool
def search_documents(
    db_path: str,
    query: Dict[str, Any],
    table_name: Optional[str] = None,
) -> Dict[str, Any]:
    db = _open_db(db_path)
    try:
        table = _get_table(db, table_name)
        docs = table.search(_build_query(query))
        return {
            "documents_toon": _to_toon_string(docs),
            "count": len(docs),
        }
    finally:
        db.close()


@mcp.tool
def contains_document(
    db_path: str,
    table_name: Optional[str] = None,
    doc_id: Optional[int] = None,
    query: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if doc_id is None and query is None:
        raise ValueError("Provide either doc_id or query")

    db = _open_db(db_path)
    try:
        table = _get_table(db, table_name)
        if doc_id is not None:
            exists = table.contains(doc_id=doc_id)
        else:
            exists = table.contains(_build_query(query))
        return {"contains": exists}
    finally:
        db.close()


@mcp.tool
def count_documents(
    db_path: str,
    query: Dict[str, Any],
    table_name: Optional[str] = None,
) -> Dict[str, Any]:
    db = _open_db(db_path)
    try:
        table = _get_table(db, table_name)
        count = table.count(_build_query(query))
        return {"count": count}
    finally:
        db.close()


@mcp.tool
def update_documents(
    db_path: str,
    fields: Dict[str, Any],
    table_name: Optional[str] = None,
    doc_ids: Optional[List[int]] = None,
    query: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if doc_ids is None and query is None:
        raise ValueError("Provide either doc_ids or query")

    db = _open_db(db_path)
    try:
        table = _get_table(db, table_name)
        if doc_ids is not None:
            updated = table.update(fields, doc_ids=doc_ids)
        else:
            updated = table.update(fields, _build_query(query))
        return {"updated_doc_ids": updated, "count": len(updated)}
    finally:
        db.close()


@mcp.tool
def upsert_documents(
    db_path: str,
    document: Dict[str, Any],
    query: Dict[str, Any],
    table_name: Optional[str] = None,
) -> Dict[str, Any]:
    db = _open_db(db_path)
    try:
        table = _get_table(db, table_name)
        affected = table.upsert(document, _build_query(query))
        return {"affected_doc_ids": affected, "count": len(affected)}
    finally:
        db.close()


@mcp.tool
def remove_documents(
    db_path: str,
    table_name: Optional[str] = None,
    doc_ids: Optional[List[int]] = None,
    query: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if doc_ids is None and query is None:
        raise ValueError("Provide either doc_ids or query")

    db = _open_db(db_path)
    try:
        table = _get_table(db, table_name)
        if doc_ids is not None:
            removed = table.remove(doc_ids=doc_ids)
        else:
            removed = table.remove(_build_query(query))
        return {"removed_doc_ids": removed, "count": len(removed)}
    finally:
        db.close()


@mcp.tool
def truncate_table(
    db_path: str,
    table_name: Optional[str] = None,
) -> Dict[str, Any]:
    db = _open_db(db_path)
    try:
        table = _get_table(db, table_name)
        table.truncate()
        return {"truncated": table_name or "_default"}
    finally:
        db.close()


@mcp.tool
def table_length(
    db_path: str,
    table_name: Optional[str] = None,
) -> Dict[str, Any]:
    db = _open_db(db_path)
    try:
        table = _get_table(db, table_name)
        return {"count": len(table)}
    finally:
        db.close()


@mcp.tool
def read_raw_db(
    db_path: str,
) -> Dict[str, Any]:
    with open(db_path, "r", encoding="utf-8") as f:
        return {"raw": json.load(f)}


@mcp.tool
def get_schema(
    db_path: str,
    table_name: Optional[str] = None,
    sample_limit: int = 1000,
) -> Dict[str, Any]:
    db = _open_db(db_path)
    try:
        table = _get_table(db, table_name)
        docs = table.all()[:sample_limit]

        paths: Dict[str, Counter] = defaultdict(Counter)
        examples: Dict[str, Any] = {}

        for doc in docs:
            normalized = _normalize_doc(doc)
            _flatten_schema_info(normalized, "", paths, examples)

        schema = {}
        for path, type_counter in sorted(paths.items()):
            schema[path] = {
                "types": dict(type_counter),
                "example": examples.get(path),
            }

        return {
            "table": table_name or "_default",
            "sampled_documents": len(docs),
            "schema": schema,
        }
    finally:
        db.close()


@mcp.tool
def close_db(db_path: str) -> Dict[str, Any]:
    db = _open_db(db_path)
    db.close()
    return {"closed": True, "db_path": db_path}


if __name__ == "__main__":
    mcp.run()
