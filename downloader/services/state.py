import json
import threading
from pathlib import Path
import time

STATE_FILE = Path("data/state.json")
_lock = threading.Lock()


def load_state():
    if not STATE_FILE.exists():
        return {"playlists": {}, "tracks": {}}
    with open(STATE_FILE, "r") as f:
        return json.load(f)


def save_state(state):
    with _lock:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)


def update_track(state, yt_id, data):
    state["tracks"][yt_id] = data
    save_state(state)


def track_exists(state, yt_id):
    return state["tracks"].get(yt_id)


def update_playlist(state, playlist_id, playlist_url, yt_ids):
    state["playlists"][playlist_id] = {
        "url": playlist_url,
        "tracks": yt_ids,
        "last_synced": time.time(),
    }
    save_state(state)