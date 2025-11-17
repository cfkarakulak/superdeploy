"""Environment routes - hardcoded environments."""

from fastapi import APIRouter
from typing import List

router = APIRouter(tags=["environments"])

# Hardcoded environments
ENVIRONMENTS = ["production", "staging"]


@router.get("/")
def list_environments() -> List[str]:
    """List all available environments."""
    return ENVIRONMENTS
