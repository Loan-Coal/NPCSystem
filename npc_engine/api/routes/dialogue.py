"""
dialogue.py - REST endpoint for full dialogue responses.

Does NOT: implement dialogue orchestration logic itself.

Dependencies injected: DialogueHandler.
"""

from fastapi import APIRouter, Depends

from api.dependencies import get_dialogue_handler
from api.schemas import DialogueRequest, DialogueResponse
from engines.dialogue.dialogue_handler import DialogueHandler


router = APIRouter()


@router.post("/dialogue", response_model=DialogueResponse)
async def dialogue(
    request: DialogueRequest,
    handler: DialogueHandler = Depends(get_dialogue_handler),
) -> DialogueResponse:
    """Run one dialogue turn and return final structured response."""

    return await handler.handle(request=request)
