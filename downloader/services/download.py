import os
import re
import shutil
import subprocess
import threading
import time
import random
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import spotipy
from dotenv import load_dotenv
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC
from spotipy.oauth2 import SpotifyClientCredentials


# -------------------- SETUP --------------------

load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

STAGING = os.getenv("MUSIC_STAGING")
LIBRARY = os.getenv("MUSIC_LIBRARY")

yt_semaphore = threading.Semaphore(2)  # limit parallel yt-dlp calls

auth = SpotifyClientCredentials(
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
)
sp = spotipy.Spotify(auth_manager=auth)


# -------------------- PLAYLIST --------------------

def fetch_track_ids(url: str) -> list[str]:
    cmd = ["yt-dlp", "--flat-playlist", "--no-warnings", "--print", "%(id)s", url]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return [x.strip() for x in result.stdout.splitlines() if x.strip()]


# -------------------- HELPERS --------------------

def clean_title(title: str) -> str:
    title = re.sub(r"\b(Lyrical|Official|Video|HD|4K)\b", "", title, flags=re.IGNORECASE)
    title = title.split("|")[0]
    title = title.replace("Title Track", "")
    title = re.sub(r"\(.*?\)", "", title)
    return title.strip()


def safe_name(s: str) -> str:
    return "".join(c for c in s if c.isalnum() or c in (" ", "-", "_")).strip()


def classify_error(stderr: str) -> str:
    s = stderr.lower()
    if any(x in s for x in ["private video", "members-only", "premium"]):
        return "private_or_premium"
    if "not available in your country" in s:
        return "region_blocked"
    if "video unavailable" in s:
        return "unavailable"
    if "age-restricted" in s:
        return "age_restricted"
    if "429" in s:
        return "rate_limited"
    return "unknown"


def is_recoverable_error(reason: str) -> bool:
    return reason in {
        "private_or_premium",
        "region_blocked",
        "unavailable",
    }


def fetch_title_from_html(video_id: str) -> str | None:
    try:
        r = requests.get(
            f"https://www.youtube.com/watch?v={video_id}",
            headers={"Accept-Language": "en-US,en;q=0.9"},
            timeout=10,
        )
        m = re.search(r'"title":\s*"([^"]+)"', r.text)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def duckduckgo_search(query: str) -> str | None:
    try:
        r = requests.get("https://html.duckduckgo.com/html/", params={"q": query}, timeout=10)
        matches = re.findall(r'class="result__a".*?>(.*?)</a>', r.text)
        if matches:
            from html import unescape
            return unescape(matches[0]).replace(" - YouTube", "").strip()
    except Exception:
        pass
    return None


def ytsearch_download(query: str, output_template: str) -> bool:
    cmd = [
        "yt-dlp",
        "--no-warnings",
        "--format", "bestaudio",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--embed-metadata",
        "--match-filter", "duration < 600",
        "--no-playlist",
        "-o", output_template,
        f"ytsearch1:{query}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode == 0


# -------------------- CORE PIPELINE --------------------

def download_and_tag(yt_id: str) -> dict:
    url = f"https://www.youtube.com/watch?v={yt_id}"
    staged_file = Path(STAGING) / f"{yt_id}.mp3"

    dl_cmd = [
        "yt-dlp",
        "--no-warnings",
        "--format", "bestaudio",
        "--extract-audio",
        "--audio-format", "mp3",
        "--audio-quality", "0",
        "--embed-metadata",
        "--no-playlist",
        "-o", f"{STAGING}/{yt_id}.%(ext)s",
        url,
    ]

    # ---------- DOWNLOAD WITH RATE LIMIT ----------
    with yt_semaphore:
        for attempt in range(3):
            dl = subprocess.run(dl_cmd, capture_output=True, text=True)

            if dl.returncode == 0:
                break

            reason = classify_error(dl.stderr)

            if reason == "rate_limited":
                time.sleep(2 ** attempt + random.random())
                continue

            if is_recoverable_error(reason):
                title_guess = fetch_title_from_html(yt_id)
                if not title_guess:
                    title_guess = duckduckgo_search(f"youtube {yt_id}")

                if not title_guess:
                    return {"status": "error", "stage": "download", "reason": reason}

                success = ytsearch_download(title_guess, f"{STAGING}/{yt_id}.%(ext)s")
                if not success:
                    return {"status": "error", "stage": "fallback_failed"}
                break

            return {"status": "error", "stage": "download", "reason": reason}

    if not staged_file.exists():
        return {"status": "error", "stage": "file_missing"}

    # ---------- SPOTIFY MATCH ----------
    audio = EasyID3(str(staged_file))

    raw_title = audio.get("title", [staged_file.stem])[0]
    raw_artist = audio.get("artist", [""])[0]

    cleaned_title = clean_title(raw_title)
    cleaned_artist = clean_title(raw_artist)

    # Construct smarter Spotify query
    if cleaned_artist:
        query = f'{cleaned_title} {cleaned_artist}'
    else:
        query = f'track:"{cleaned_title}"'
    print(query)
    results = sp.search(q=query, type="track", limit=5)

    if not results["tracks"]["items"]:
        staged_file.unlink(missing_ok=True)
        return {"status": "error", "stage": "spotify_no_match"}

    track = results["tracks"]["items"][0]

    spotify_id = track["id"]     
    
    title = track["name"]
    artist = ", ".join(a["name"] for a in track["artists"])
    album = track["album"]["name"]
    year = track["album"]["release_date"][:4]
    cover_url = track["album"]["images"][0]["url"]

    # ---------- WRITE TAGS ----------
    audio["title"] = title
    audio["artist"] = artist
    audio["album"] = album
    audio["date"] = year
    audio.save()

    image_data = requests.get(cover_url).content
    id3 = ID3(str(staged_file))
    id3.delall("APIC")
    id3.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=image_data))
    id3.save()

    # ---------- MOVE ----------
    album_safe = safe_name(album) or "Unknown"
    title_safe = safe_name(title)

    dest_dir = Path(LIBRARY) / album_safe # type: ignore
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest_file = dest_dir / f"{title_safe}.mp3"
    counter = 1
    while dest_file.exists():
        dest_file = dest_dir / f"{title_safe} ({counter}).mp3"
        counter += 1

    shutil.move(str(staged_file), str(dest_file))
    relative_path = str(dest_file.relative_to(LIBRARY))
    
    return {
        "status": "ok",
        "yt_id": yt_id,
        "spotify_id": spotify_id,
        "title": title,
        "album": album,
        "track_path": relative_path,
    }


# -------------------- PLAYLIST RUNNER --------------------

def process_playlist(url: str, workers: int = 4):
    ids = fetch_track_ids(url)
    results = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(download_and_tag, i): i for i in ids}
        for future in as_completed(futures):
            result = future.result()
            print(result)
            results.append(result)

    return results