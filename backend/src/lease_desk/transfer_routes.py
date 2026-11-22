from fastapi import APIRouter, Depends, Response

from ..auth import current_user, require_roles
from . import transfers
from .transfer_schemas import ReversalIn, TransferIn

router = APIRouter(prefix='/lease-desk/budget-transfers', tags=['预算转拨流水'])
analyst = require_roles('analyst')


@router.get('')
def board(_user=Depends(current_user)):
    return transfers.board()


@router.post('', status_code=201)
def transfer(payload: TransferIn, response: Response, user=Depends(analyst)):
    result = transfers.create(payload, user)
    if result['replayed']:
        response.status_code = 200
    return result


@router.post('/{transfer_id}/reverse')
def reverse(transfer_id: int, payload: ReversalIn, user=Depends(analyst)):
    return transfers.reverse(transfer_id, payload, user)
