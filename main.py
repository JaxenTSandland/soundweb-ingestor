import os

from services.lastfm import (
    fetch_top_artists,
    fetch_artist_details,
)
from services.musicbrainz import fetch_artist_genre_data
from services.spotify import fetch_spotify_data
from services.combine_artist_data import combine_top_artist_data, implement_genre_data
from services.neo4j_export import export_artist_data_to_neo4j
from services.mysql_export import export_genres_to_mysql

from model.artist_node import ArtistNode
from utils.checkpoint import save_checkpoint, load_checkpoint

ENV = os.getenv("ENV", "production")
LOCAL_ENV = ENV == "local"
WRITE_TO_FILE = LOCAL_ENV

RELOAD_LASTFM = True if LOCAL_ENV else True
RELOAD_MUSICBRAINZ = True if LOCAL_ENV else True
RELOAD_SPOTIFY = True if LOCAL_ENV else True
EXPORT_TO_NEO4J = True if LOCAL_ENV else True
EXPORT_TO_MYSQL = True if LOCAL_ENV else True


def main():
    # generate_custom_artist_data(
    #     name="La la land",
    #     spotify_id=None
    # )
    generate_top_artist_data()


def generate_top_artist_data(max_artists:int=1000):
    artists: list[ArtistNode] = []

    if RELOAD_LASTFM:
        print("[MAIN] Fetching top artists from Last.fm...")
        artists = fetch_top_artists(max_artists=max_artists)
        if WRITE_TO_FILE:
            save_checkpoint(artists, "lastfm_top")

        print("\n[MAIN] Fetching detailed info from Last.fm...")
        artists = fetch_artist_details(artists)
        if WRITE_TO_FILE:
            save_checkpoint(artists, "lastfm_detailed")

        print(f"\n[MAIN] Collected detailed info for {len(artists)} artists.")
    else:
        artists = load_checkpoint('lastfm_detailed')
        print(f"\n[MAIN] Loaded top artists from Last.fm detailed json file")

    if RELOAD_MUSICBRAINZ:
        print("\n[MAIN] Fetching genre data from MusicBrainz...")
        artists = fetch_artist_genre_data(artists)
        if WRITE_TO_FILE:
            save_checkpoint(artists, "musicbrainz")
        print(f"[MAIN] Collected MusicBrainz genre info for {len(artists)} artists.")
    else:
        artists = load_checkpoint('musicbrainz')
        print(f"\n[MAIN] Loaded top artists from MusicBrainz detailed json file")

    if RELOAD_SPOTIFY:
        print("\n[MAIN] Fetching Spotify data...")
        artists = fetch_spotify_data(artists)
        if WRITE_TO_FILE:
            save_checkpoint(artists, "spotify")
        print(f"[MAIN] Collected Spotify info for {len(artists)} artists.")
    else:
        artists = load_checkpoint('spotify')
        print(f"\n[MAIN] Loaded top artists from Spotify detailed json file")

    print("\n[MAIN] Finalizing artist nodes (calculate x/y/color)...")
    artists = implement_genre_data(artists, top_artists=True)
    if WRITE_TO_FILE:
        save_checkpoint(artists, "final_genre_combined")
    print(f"[MAIN] Finalized {len(artists)} artist nodes wth proper genre data implemented.")

    if EXPORT_TO_NEO4J:
        print("\n[MAIN] Exporting artists to Neo4j...")
        export_artist_data_to_neo4j(artists, write_to_file=WRITE_TO_FILE, add_top_artist_label=True)

    if EXPORT_TO_MYSQL:
        print("\n[MAIN] Exporting genres to MySQL...")
        export_genres_to_mysql()



def generate_custom_artist_data(name: str = None, spotify_id: str = None, mbid: str = None):
    if not spotify_id and not name:
        raise ValueError("[MAIN] spotify_id or artist name is required for custom artist ingestion.")

    print(f"[MAIN] Starting custom artist ingestion for {name} (SpotifyID: {spotify_id})...")


    artist = ArtistNode(
        id=spotify_id,
        name=name,
        spotifyId=spotify_id,
        lastfmMBID=mbid,
        genres=[],
        userTags=[],
        relatedArtists=[],
    )

    artists = [artist]


    print("[MAIN] Fetching Spotify details...")
    artists = fetch_spotify_data(artists, write_to_file=False)

    print("[MAIN] Fetching Last.fm details...")
    artists = fetch_artist_details(artists, write_to_file=False)

    print("\n[MAIN] Fetching genre data from MusicBrainz...")
    artists = fetch_artist_genre_data(artists, write_to_file=False)

    print("[MAIN] Combining final data...")
    artists = implement_genre_data(artists, top_artists=False)

    #print(artists)

    print("[MAIN] Exporting to Neo4j...")
    export_artist_data_to_neo4j(artists, write_to_file=False, add_top_artist_label=False)

    print(f"[MAIN] Finished ingesting {name}.")


if __name__ == "__main__":
    main()
