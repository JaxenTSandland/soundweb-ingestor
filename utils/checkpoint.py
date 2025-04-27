import json
import os
from model.artist_node import ArtistNode

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
temp_dir = os.path.join(project_root, "data", "temp")
data_dir = os.path.join(project_root, "data")

os.makedirs(temp_dir, exist_ok=True)

checkpoint_paths = {
    "lastfm_top": os.path.join(temp_dir, "1_lastfm_top_artists.json"),
    "lastfm_detailed": os.path.join(temp_dir, "2_lastfm_expanded_artist_data.json"),
    "musicbrainz": os.path.join(temp_dir, "3_musicbrainz_genres_added.json"),
    "spotify": os.path.join(temp_dir, "4_spotify_enriched_artist_data.json"),
    "final_genre_combined": os.path.join(temp_dir, "5_combined_final_artist_data.json"),
    "genre_map": os.path.join(data_dir, "genreMap.json")
}

def save_checkpoint(artists: list[ArtistNode], stage_name: str):
    path = checkpoint_paths.get(stage_name)
    if not path:
        raise ValueError(f"No checkpoint path configured for stage '{stage_name}'")

    with open(path, "w", encoding="utf-8") as f:
        json.dump([artist.to_dict() for artist in artists], f, indent=2)
    print(f"[CHECKPOINT] Saved {len(artists)} artists to {os.path.basename(path)}")

def load_checkpoint(stage_name: str) -> list[ArtistNode]:
    path = checkpoint_paths.get(stage_name)
    if not path:
        raise ValueError(f"No checkpoint path configured for stage '{stage_name}'")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"[CHECKPOINT] Loaded {len(data)} artists from {os.path.basename(path)}")
    return [ArtistNode(**artist) for artist in data]
