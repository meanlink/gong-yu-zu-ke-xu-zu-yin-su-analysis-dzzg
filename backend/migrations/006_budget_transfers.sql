CREATE TABLE IF NOT EXISTS budget_transfer (
    id integer GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    idempotency_key text NOT NULL UNIQUE,
    neighborhood text NOT NULL,
    from_budget_id integer NOT NULL REFERENCES retention_budget(id),
    to_budget_id integer NOT NULL REFERENCES retention_budget(id),
    amount_cents bigint NOT NULL CHECK (amount_cents>0),
    note text NOT NULL,
    status text NOT NULL DEFAULT 'posted' CHECK (status IN ('posted','reversed')),
    created_by integer NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    reversed_by integer REFERENCES users(id),
    reversed_at timestamptz,
    reversal_note text,
    CHECK (from_budget_id<>to_budget_id),
    CHECK (status='posted' OR (reversed_by IS NOT NULL AND reversed_at IS NOT NULL AND reversal_note IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS budget_transfer_from ON budget_transfer(from_budget_id);
CREATE INDEX IF NOT EXISTS budget_transfer_to ON budget_transfer(to_budget_id);
