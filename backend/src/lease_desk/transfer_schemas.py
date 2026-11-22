from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from .offer_schemas import Note

Key = Annotated[str, StringConstraints(strip_whitespace=True, min_length=8, max_length=100)]


class TransferIn(BaseModel):
    idempotency_key: Key
    from_budget_id: int = Field(gt=0)
    to_budget_id: int = Field(gt=0)
    amount_cents: int = Field(gt=0, le=1_000_000_000)
    note: Note


class ReversalIn(BaseModel):
    note: Note
