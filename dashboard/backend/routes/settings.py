"""Settings management routes."""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from database import get_db
from models import Setting

router = APIRouter(tags=["settings"])


class GitHubTokenRequest(BaseModel):
    """Request to set GitHub token."""

    token: str


class GitHubTokenResponse(BaseModel):
    """Response with GitHub token."""

    token: Optional[str] = None
    configured: bool


@router.get("/github-token", response_model=GitHubTokenResponse)
async def get_github_token(db: Session = Depends(get_db)):
    """Get stored GitHub token from database."""
    try:
        setting = db.query(Setting).filter(Setting.key == "github_token").first()
        if setting and setting.value:
            return GitHubTokenResponse(token=setting.value, configured=True)
    except Exception as e:
        print(f"Error fetching GitHub token: {e}")

    return GitHubTokenResponse(token=None, configured=False)


@router.post("/github-token")
async def set_github_token(request: GitHubTokenRequest, db: Session = Depends(get_db)):
    """Store GitHub token in database."""
    try:
        setting = db.query(Setting).filter(Setting.key == "github_token").first()
        
        if setting:
            setting.value = request.token
        else:
            setting = Setting(key="github_token", value=request.token, encrypted=0)
            db.add(setting)
        
        db.commit()
        return {"message": "GitHub token saved successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/github-token")
async def delete_github_token(db: Session = Depends(get_db)):
    """Delete stored GitHub token from database."""
    try:
        setting = db.query(Setting).filter(Setting.key == "github_token").first()
        if setting:
            db.delete(setting)
            db.commit()
        
        return {"message": "GitHub token deleted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))
