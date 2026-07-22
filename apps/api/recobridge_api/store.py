import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Protocol
from uuid import uuid4


class EventStoreUnavailable(RuntimeError):
    pass


class IdempotencyConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredEvent:
    event_id: str
    duplicate: bool


class EventStore(Protocol):
    def initialize(self) -> None: ...

    def check(self) -> str: ...

    def write(self, endpoint: str, idempotency_key: str, payload: dict[str, Any]) -> StoredEvent: ...

    def close(self) -> None: ...


def canonical_payload(payload: dict[str, Any]) -> tuple[str, str]:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return serialized, hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class MemoryEventStore:
    def __init__(self) -> None:
        self._events: dict[tuple[str, str], tuple[str, str]] = {}
        self._lock = Lock()

    def initialize(self) -> None:
        return None

    def check(self) -> str:
        return "ok"

    def write(self, endpoint: str, idempotency_key: str, payload: dict[str, Any]) -> StoredEvent:
        _, payload_hash = canonical_payload(payload)
        key = (endpoint, idempotency_key)
        with self._lock:
            existing = self._events.get(key)
            if existing:
                event_id, existing_hash = existing
                if existing_hash != payload_hash:
                    raise IdempotencyConflict("idempotency key was already used with another payload")
                return StoredEvent(event_id=event_id, duplicate=True)
            event_id = str(uuid4())
            self._events[key] = (event_id, payload_hash)
            return StoredEvent(event_id=event_id, duplicate=False)

    def close(self) -> None:
        return None


class PostgresEventStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    @staticmethod
    def _connect(database_url: str):
        import psycopg

        return psycopg.connect(database_url, connect_timeout=3)

    def initialize(self) -> None:
        migration = Path(__file__).resolve().parents[1] / "migrations" / "001_init.sql"
        try:
            with self._connect(self.database_url) as connection:
                connection.execute(migration.read_text(encoding="utf-8"))
        except Exception as exc:
            raise EventStoreUnavailable("cannot initialize PostgreSQL event store") from exc

    def check(self) -> str:
        try:
            with self._connect(self.database_url) as connection:
                table = connection.execute("SELECT to_regclass('public.event_ingestion')").fetchone()
            return "ok" if table and table[0] is not None else "unavailable"
        except Exception:
            return "unavailable"

    def write(self, endpoint: str, idempotency_key: str, payload: dict[str, Any]) -> StoredEvent:
        serialized, payload_hash = canonical_payload(payload)
        event_id = str(uuid4())
        try:
            with self._connect(self.database_url) as connection:
                inserted = connection.execute(
                    """
                    INSERT INTO event_ingestion
                        (event_id, endpoint, idempotency_key, payload_hash, payload, occurred_at)
                    VALUES (%s, %s, %s, %s, %s::jsonb, (%s::jsonb->>'occurred_at')::timestamptz)
                    ON CONFLICT (endpoint, idempotency_key) DO NOTHING
                    RETURNING event_id, payload_hash
                    """,
                    (event_id, endpoint, idempotency_key, payload_hash, serialized, serialized),
                ).fetchone()
                if inserted:
                    return StoredEvent(event_id=str(inserted[0]), duplicate=False)

                existing = connection.execute(
                    "SELECT event_id, payload_hash FROM event_ingestion WHERE endpoint = %s AND idempotency_key = %s",
                    (endpoint, idempotency_key),
                ).fetchone()
                if existing is None:
                    raise EventStoreUnavailable("event conflict could not be resolved")
                if existing[1] != payload_hash:
                    raise IdempotencyConflict("idempotency key was already used with another payload")
                return StoredEvent(event_id=str(existing[0]), duplicate=True)
        except IdempotencyConflict:
            raise
        except EventStoreUnavailable:
            raise
        except Exception as exc:
            raise EventStoreUnavailable("PostgreSQL event write failed") from exc

    def close(self) -> None:
        return None


def create_event_store(database_url: str) -> EventStore:
    if database_url == "memory://":
        return MemoryEventStore()
    return PostgresEventStore(database_url)
