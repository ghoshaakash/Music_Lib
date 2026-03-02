# run_playlist.py
from downloader.services.playlist import process_playlist

process_playlist(
    "https://www.youtube.com/watch?v=PXDlU0YDQ6U&list=PLIXu6h0Wo1JV9oL13aIi2gGZF5BrmRbSC&pp=sAgC",
    workers=4
)