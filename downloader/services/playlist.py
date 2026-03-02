from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import parse_qs, urlparse

from .download import download_and_tag
from .state import (
    load_state,
    update_track,
    track_exists,
    update_playlist,
)


def extract_playlist_id(url: str) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query)
    return qs.get("list", [""])[0]


def fetch_track_ids(url: str) -> list[str]:
    import subprocess

    cmd = ["yt-dlp", "--flat-playlist", "--no-warnings", "--print", "%(id)s", url]
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(result.stderr)

    return [x.strip() for x in result.stdout.splitlines() if x.strip()]


def process_playlist(url: str, workers: int = 4):

    state = load_state()

    playlist_id = extract_playlist_id(url)
    yt_ids = fetch_track_ids(url)

    # Update playlist metadata
    update_playlist(state, playlist_id, url, yt_ids)

    with ThreadPoolExecutor(max_workers=workers) as executor:

        futures = {}

        for yt_id in yt_ids:

            existing = track_exists(state, yt_id)

            # Skip if file exists
            if existing:
                file_path = Path("data/library") / existing["file_path"]
                if file_path.exists():
                    print(f"✓ Skipping {yt_id}")
                    continue

            futures[executor.submit(download_and_tag, yt_id)] = yt_id

        for future in as_completed(futures):
            yt_id = futures[future]
            result = future.result()

            if result["status"] == "ok":
                update_track(state, yt_id, {
                    "spotify_id": result["spotify_id"],
                    "title": result["title"],
                    "album": result["album"],
                    "file_path": result["track_path"],
                })
                print(f"✔ Added {yt_id}")
            else:
                print(f"✗ Failed {yt_id}: {result}")