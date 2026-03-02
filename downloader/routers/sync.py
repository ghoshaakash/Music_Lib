from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import services.download as download_service
import services.playlist as playlist_service

router = APIRouter(prefix="/sync", tags=["sync"])


class SyncRequest(BaseModel):
    playlist_id: int


@router.post("/fetch-tracks/{playlist_id}")
def fetch_tracks(playlist_id: int):
    """Fetch track IDs from YouTube and store in playlists.json"""
    playlists = playlist_service.read_all()
    match = next((p for p in playlists if p["id"] == playlist_id), None)

    if not match:
        raise HTTPException(status_code=404, detail="Playlist not found")

    try:
        ids = download_service.fetch_track_ids(match["url"])
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    match["tracks"] = [{"yt_id": i, "downloaded": False} for i in ids]
    playlist_service.write_all(playlists)

    return {"playlist": match["name"], "track_count": len(ids), "tracks": match["tracks"]}


@router.post("/download/{yt_id}")
def download_track(yt_id: str):
    """Download and tag a single track"""
    result = download_service.download_and_tag(yt_id)

    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result)

    return result