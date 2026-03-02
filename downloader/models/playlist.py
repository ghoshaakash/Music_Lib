from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class PlaylistIn(BaseModel):
    """What we expect FROM the UI when adding a playlist"""
    name: str
    url: str

class Playlist(BaseModel):
    """The full playlist object stored in our JSON"""
    id: int
    name: str
    url: str
    last_synced: Optional[datetime] = None
    tracks: list = []