CREATE TABLE IF NOT EXISTS event_ingestion (
    event_id UUID PRIMARY KEY,
    endpoint VARCHAR(32) NOT NULL,
    idempotency_key VARCHAR(128) NOT NULL,
    payload_hash CHAR(64) NOT NULL,
    payload JSONB NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (endpoint, idempotency_key)
);

CREATE INDEX IF NOT EXISTS event_ingestion_request_id_idx
    ON event_ingestion ((payload->>'request_id'));

CREATE INDEX IF NOT EXISTS event_ingestion_created_at_idx
    ON event_ingestion (created_at DESC);
