from services.lastfm import (
    fetch_top_artists as lastfm_fetch_top_artists,
    fetch_artist_details as lastfm_fetch_artist_details,
)
from services.musicbrainz import fetch_artist_genre_data as musicbrainz_fetch_artist_genre_data
from services.spotify import fetch_spotify_data as spotify_fetch_spotify_data
from services.combine_artist_data import combine_all_artist_data

WRITE_TO_FILE = True
RELOAD_LASTFM = False
RELOAD_MUSICBRAINZ = False
RELOAD_SPOTIFY = True

def main():
    lastfm_top_artist_data = None
    lastfm_detailed_artist_data = None
    if RELOAD_LASTFM:
        print("Fetching top artists from Last.fm...")
        lastfm_top_artist_data = lastfm_fetch_top_artists(write_to_file=WRITE_TO_FILE)

        print("\nFetching detailed info for top artists...")
        lastfm_detailed_artist_data = lastfm_fetch_artist_details(write_to_file=WRITE_TO_FILE)

        print(f"\nCollected {len(lastfm_top_artist_data)} top artists")
        print(f"Collected {len(lastfm_detailed_artist_data)} detailed artist entries")


    musicbrainz_artist_data = None
    if RELOAD_MUSICBRAINZ:
        print("\nFetching genre data from MusicBrainz...")
        musicbrainz_artist_data = musicbrainz_fetch_artist_genre_data(write_to_file=WRITE_TO_FILE, top_artists=lastfm_top_artist_data)

        print(f"Collected genre info for {len(musicbrainz_artist_data)} artists")


    spotify_artist_data = None
    if RELOAD_SPOTIFY:
        print("\nFetching Spotify data...")
        spotify_artist_data = spotify_fetch_spotify_data(
            write_to_file=WRITE_TO_FILE,
            lastfm_artists=lastfm_detailed_artist_data
        )
        print(f"Collected Spotify info for {len(spotify_artist_data)} artists")


    print("\nCombining all data sources into unified dataset...")
    combined_artist_data = combine_all_artist_data(
        write_to_file=WRITE_TO_FILE,
        lastfm_artists=lastfm_detailed_artist_data,
        spotify_artists=spotify_artist_data,
        musicbrainz_artists=musicbrainz_artist_data
    )
    print(f"Combined dataset contains {len(combined_artist_data)} artists")




if __name__ == "__main__":
    main()
