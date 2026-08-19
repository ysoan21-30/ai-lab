"""Portable UUID column type: native UUID on PostgreSQL, CHAR(36) elsewhere
(e.g. SQLite in tests), so the same models work in both environments.
"""
import uuid

from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import CHAR, TypeDecorator


class GUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=False))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if dialect.name == "postgresql":
            return str(value)
        if not isinstance(value, str):
            return str(value)
        return value

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return str(value)
