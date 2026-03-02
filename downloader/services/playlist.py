import json
import os
from datetime import datetime

PLAYLISTS_FILE = os.path.join(os.path.dirname(__file__), "../config/playlists.json")


def read_all() -> list:
    """Read playlists from JSON file"""
    with open(PLAYLISTS_FILE, "r") as f:
        return json.load(f)


def write_all(data: list) -> None:
    """Write playlists back to JSON file"""
    with open(PLAYLISTS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def add(name: str, url: str) -> dict:
    """Add a new playlist, return it"""
    playlists = read_all()

    new_id = max((p["id"] for p in playlists), default=0) + 1

    entry = {
        "id": new_id,
        "name": name,
        "url": url,
        "last_synced": None,
        "tracks": []
    }

    playlists.append(entry)
    write_all(playlists)
    return entry


def delete(playlist_id: int) -> bool:
    """Remove playlist by id, return True if found"""
    playlists = read_all()

    match = next((p for p in playlists if p["id"] == playlist_id), None)
    if not match:
        return False

    write_all([p for p in playlists if p["id"] != playlist_id])
    return True


def mark_synced(playlist_id: int) -> None:
    """Update last_synced timestamp after a successful sync"""
    playlists = read_all()

    for p in playlists:
        if p["id"] == playlist_id:
            p["last_synced"] = datetime.now().isoformat()
            break

    write_all(playlists)