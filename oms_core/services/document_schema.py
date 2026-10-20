"""Machine-checkable schema for a schema 2 observation document.

Hand-rolled ``isinstance`` chains were getting long and drifted from the
architecture document. This module states the contract once, in JSON Schema,
so an imported file is either accepted with evidence or rejected with a
message that names the offending path.
"""

from __future__ import annotations

from typing import Any

import jsonschema

from oms_core.services import document_map as dm
from oms_core.services import synoptic as synoptic_service

#: The eight hours of the synoptic day.
_HOURS = list(synoptic_service.HOURS)

#: Every group name the mapping table knows (the 44 fields).
_GROUP_NAMES = [synop for _form, synop in dm.SYNOP_FIELDS]

#: One stored hour: the observer is mandatory (empty string allowed, R3), the
#: observed values are optional, and a group is at most five digits or '/'.
_HOUR_SCHEMA = {
    "type": "object",
    "required": ["observador"],
    "properties": {
        "observador": {"type": "string"},
        "datos": {
            "type": "object",
            "additionalProperties": {"type": ["string", "number", "null"]},
        },
        "grupos": {
            "type": "object",
            "propertyNames": {"enum": _GROUP_NAMES},
            "additionalProperties": {
                "type": ["string", "number"],
                "maxLength": 5,
                "pattern": "^[0-9/]*$",
            },
        },
    },
    "additionalProperties": True,
}

#: The document the application writes and the tree carries.
DOCUMENT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "OMS observation day (schema 2)",
    "type": "object",
    "required": ["schema", "meta"],
    "properties": {
        "schema": {"const": 2},
        "meta": {
            "type": "object",
            "required": ["estacion", "fecha"],
            "properties": {
                "estacion": {"type": "string", "minLength": 1},
                "fecha": {"type": "string", "pattern": r"^\d{4}-\d{2}-\d{2}$"},
                "actualizado": {"type": "string"},
                "cerrado_en": {"type": ["string", "null"]},
            },
            "additionalProperties": True,
        },
        "synop": {
            "type": "object",
            "propertyNames": {"enum": _HOURS},
            "additionalProperties": _HOUR_SCHEMA,
        },
        "horas": {  # tolerated container, same shape
            "type": "object",
            "propertyNames": {"enum": _HOURS},
            "additionalProperties": _HOUR_SCHEMA,
        },
        "cli": {"type": "object"},
    },
    "additionalProperties": True,
    "anyOf": [{"required": ["synop"]}, {"required": ["horas"]}],
}

_VALIDATOR = jsonschema.Draft202012Validator(DOCUMENT_SCHEMA)


class DocumentSchemaError(ValueError):
    """A document does not satisfy the schema 2 contract."""


def validate_document_schema(document: object) -> None:
    """Raise :class:`DocumentSchemaError` naming the first broken path."""
    if not isinstance(document, dict):
        raise DocumentSchemaError("el documento no es un objeto JSON")
    errors = sorted(_VALIDATOR.iter_errors(document), key=lambda e: list(e.absolute_path))
    if not errors:
        return
    first = errors[0]
    where = "/".join(str(part) for part in first.absolute_path) or "(raíz)"
    raise DocumentSchemaError(f"{where}: {first.message}")


def is_schema_two(document: object) -> bool:
    """True when the document declares the current schema."""
    try:
        return int(document.get("schema") or 1) >= 2  # type: ignore[union-attr]
    except (AttributeError, TypeError, ValueError):
        return False


__all__ = [
    "DOCUMENT_SCHEMA",
    "DocumentSchemaError",
    "is_schema_two",
    "validate_document_schema",
]
