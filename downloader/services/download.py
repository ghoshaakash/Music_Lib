import subprocess
from dotenv import load_dotenv
import os

# find .env relative to this file's location, not where you run from
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

STAGING = os.getenv("MUSIC_STAGING")
LIBRARY = os.getenv("MUSIC_LIBRARY")
BEETS_CONFIG = os.path.join(os.path.dirname(__file__), "../config/beets.yaml")


def fetch_track_ids(url: str) -> list[str]:
    cmd: list[str] = [
        "yt-dlp", "--flat-playlist", "--no-warnings", "--print", "%(id)s", url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed: {result.stderr}")
    
    ids = [line.strip() for line in result.stdout.strip().split("\n") if line.strip()]
    return ids

def download_and_tag(yt_id: str) -> dict[str, str]:
    url = f"https://www.youtube.com/watch?v={yt_id}"

    dl_cmd: list[str] = [
        "yt-dlp",
        "--no-warnings",
        "--format", "bestaudio",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--embed-thumbnail",
        "--embed-metadata",
        "--no-playlist",
        "-o", f"{STAGING}/%(title)s.%(ext)s",
        url
    ]
    dl = subprocess.run(dl_cmd, capture_output=True, text=True)
    
    if dl.returncode != 0:
        return {"status": "error", "stage": "download", "detail": dl.stderr}

    beet_cmd: list[str] = [
        "beet", "--config", BEETS_CONFIG, "import", "--quiet", str(STAGING)
    ]
    beet = subprocess.run(beet_cmd, capture_output=True, text=True)
    
    if beet.returncode != 0:
        return {"status": "error", "stage": "beets", "detail": beet.stderr}

    return {"status": "ok", "yt_id": yt_id}