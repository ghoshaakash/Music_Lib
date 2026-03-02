from fastapi import APIRouter, HTTPException
from models.playlist import PlaylistIn
import services.playlist as playlist_service

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("/")
def get_sources():
    """Return all playlists"""
    return playlist_service.read_all()


@router.post("/")
def add_source(playlist: PlaylistIn):
    """Add a new playlist"""
    if "youtube.com" not in playlist.url and "youtu.be" not in playlist.url:
        raise HTTPException(status_code=400, detail="YouTube URLs only")

    return playlist_service.add(playlist.name, playlist.url)


@router.delete("/{playlist_id}")
def delete_source(playlist_id: int):
    """Delete a playlist by id"""
    deleted = playlist_service.delete(playlist_id)

    if not deleted:
        raise HTTPException(status_code=404, detail="Playlist not found")

    return {"deleted": playlist_id}