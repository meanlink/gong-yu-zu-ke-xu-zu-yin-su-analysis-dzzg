from fastapi import HTTPException
from psycopg.errors import UniqueViolation

from ..db import connect
from ..resident_operations import audit, get
from .budgets import committed

LEDGER = '''SELECT t.id,t.idempotency_key,t.neighborhood,t.amount_cents,t.note,t.status,
    t.created_at,t.reversed_at,t.reversal_note,
    t.from_budget_id,f.starts_month AS from_month,t.to_budget_id,r.starts_month AS to_month,
    c.full_name AS created_by_name,u.full_name AS reversed_by_name
    FROM budget_transfer t
    JOIN retention_budget f ON f.id=t.from_budget_id
    JOIN retention_budget r ON r.id=t.to_budget_id
    JOIN users c ON c.id=t.created_by
    LEFT JOIN users u ON u.id=t.reversed_by'''


def board():
    with connect() as conn:
        rows = conn.execute(LEDGER + ' ORDER BY t.id DESC').fetchall()
    return {'transfers': rows}


def lock_pair(conn, from_id, to_id):
    # Always lock budget rows in ascending id order so concurrent transfers
    # (and offer approvals locking a single budget row) cannot deadlock.
    rows = {}
    for budget_id in sorted({from_id, to_id}):
        rows[budget_id] = get(conn, 'SELECT * FROM retention_budget WHERE id=%s FOR UPDATE', (budget_id,), '片区让利预算不存在')
    return rows


def remaining(conn, budget):
    return budget['cap_cents'] - committed(conn, budget['id'])


def create(payload, user):
    try:
        with connect() as conn:
            existing = conn.execute(LEDGER + ' WHERE t.idempotency_key=%s', (payload.idempotency_key,)).fetchone()
            if existing:
                return {**existing, 'replayed': True}
            if payload.from_budget_id == payload.to_budget_id:
                raise HTTPException(422, '转出与接收不能是同一预算月')
            budgets = lock_pair(conn, payload.from_budget_id, payload.to_budget_id)
            source, target = budgets[payload.from_budget_id], budgets[payload.to_budget_id]
            if source['neighborhood'] != target['neighborhood']:
                raise HTTPException(422, '只能在同一片区的启租月之间转拨额度')
            if remaining(conn, source) < payload.amount_cents:
                raise HTTPException(409, '转出月可用余额不足，转拨未执行')
            conn.execute('UPDATE retention_budget SET cap_cents=cap_cents-%s WHERE id=%s', (payload.amount_cents, source['id']))
            conn.execute('UPDATE retention_budget SET cap_cents=cap_cents+%s WHERE id=%s', (payload.amount_cents, target['id']))
            row = conn.execute('''INSERT INTO budget_transfer(idempotency_key,neighborhood,from_budget_id,to_budget_id,amount_cents,note,created_by)
                VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id''',
                (payload.idempotency_key, source['neighborhood'], source['id'], target['id'],
                 payload.amount_cents, payload.note, user['id'])).fetchone()
            audit(conn, user, 'budget_transfer_posted', 'budget_transfer', row['id'], payload.note)
            out = conn.execute(LEDGER + ' WHERE t.id=%s', (row['id'],)).fetchone()
        return {**out, 'replayed': False}
    except UniqueViolation:
        # A concurrent retry with the same key committed first; our transaction
        # rolled back, so both months stay untouched. Return the original record.
        with connect() as conn:
            row = conn.execute(LEDGER + ' WHERE t.idempotency_key=%s', (payload.idempotency_key,)).fetchone()
        if row:
            return {**row, 'replayed': True}
        raise


def reverse(transfer_id, payload, user):
    with connect() as conn:
        row = get(conn, 'SELECT * FROM budget_transfer WHERE id=%s FOR UPDATE', (transfer_id,), '转拨流水不存在')
        if row['status'] == 'reversed':
            raise HTTPException(409, '该笔转拨已冲回')
        budgets = lock_pair(conn, row['from_budget_id'], row['to_budget_id'])
        if remaining(conn, budgets[row['to_budget_id']]) < row['amount_cents']:
            raise HTTPException(409, '接收月可用余额不足，整笔冲回被拒绝')
        conn.execute('UPDATE retention_budget SET cap_cents=cap_cents+%s WHERE id=%s', (row['amount_cents'], row['from_budget_id']))
        conn.execute('UPDATE retention_budget SET cap_cents=cap_cents-%s WHERE id=%s', (row['amount_cents'], row['to_budget_id']))
        conn.execute("UPDATE budget_transfer SET status='reversed',reversed_by=%s,reversed_at=now(),reversal_note=%s WHERE id=%s",
                     (user['id'], payload.note, transfer_id))
        audit(conn, user, 'budget_transfer_reversed', 'budget_transfer', transfer_id, payload.note)
        out = conn.execute(LEDGER + ' WHERE t.id=%s', (transfer_id,)).fetchone()
    return out
