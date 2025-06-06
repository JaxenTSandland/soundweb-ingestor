import os
import json
from typing import List

from model.artist_node import ArtistNode

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
data_dir = os.path.join(project_root, "data")
temp_dir = os.path.join(data_dir, "temp")
os.makedirs(temp_dir, exist_ok=True)

lastfm_path = os.path.join(temp_dir, "lastfmArtists.json")
spotify_path = os.path.join(temp_dir, "spotifyArtists.json")
musicbrainz_path = os.path.join(temp_dir, "musicBrainzArtists.json")
genre_map_path = os.path.join(data_dir, "genreMap.json")
output_path = os.path.join(temp_dir, "artistData.json")


def normalize_name(name):
    return ''.join(c.lower() for c in name if c.isalnum()).strip()



def combine_top_artist_data(
    write_to_file=False,
    lastfm_artists=None,
    spotify_artists=None,
    musicbrainz_artists=None
) -> List[ArtistNode]:
    if lastfm_artists is None:
        with open(lastfm_path, "r", encoding="utf-8") as f:
            lastfm_artists = json.load(f)
    if spotify_artists is None:
        with open(spotify_path, "r", encoding="utf-8") as f:
            spotify_artists = json.load(f)
    if musicbrainz_artists is None:
        with open(musicbrainz_path, "r", encoding="utf-8") as f:
            musicbrainz_artists = json.load(f)

    with open(genre_map_path, "r", encoding="utf-8") as f:
        genre_map = json.load(f)

    lastfm_map = {normalize_name(a["name"]): a for a in lastfm_artists}
    musicbrainz_map = {normalize_name(a["name"]): a for a in musicbrainz_artists}

    seen = set()
    merged: List[ArtistNode] = []
    rankScore = 1

    for spotify in spotify_artists:
        norm_name = normalize_name(spotify["name"])
        if norm_name in seen:
            continue
        seen.add(norm_name)

        lastfm = lastfm_map.get(norm_name)
        mb = musicbrainz_map.get(norm_name)
        if not lastfm and not mb:
            continue

        # Genre resolution
        genre_scores = {}
        for source in [lastfm, spotify, mb]:
            if source and "genres" in source:
                for idx, genre in enumerate(source["genres"][:3]):
                    g = genre.lower()
                    if g in genre_map:
                        genre_scores[g] = genre_scores.get(g, 0) + (3 - idx)

        genres = sorted(genre_scores.items(), key=lambda x: x[1], reverse=True)
        genres = [g for g, _ in genres]

        if not genres:
            continue

        top_genre = genres[0]
        color = genre_map.get(top_genre, {}).get("color", "#cccccc")

        # Coordinate calculation
        x_total = 0
        y_total = 0
        weight_total = 0
        for idx, g in enumerate(genres[:10]):
            g_data = genre_map.get(g)
            if g_data and "x" in g_data and "y" in g_data:
                weight = 1 / (idx + 1)
                x_total += g_data["x"] * weight
                y_total += g_data["y"] * weight
                weight_total += weight

        x = x_total / weight_total if weight_total else None
        y = y_total / weight_total if weight_total else None
        image_url = spotify.get("imageUrl") or (lastfm.get("imageUrl") if lastfm else None)

        artist_node = ArtistNode(
            id=spotify.get("spotifyId"),
            name=spotify["name"],
            genres=genres,
            popularity=spotify.get("popularity", 0),
            spotifyId=spotify.get("spotifyId"),
            spotifyUrl=spotify.get("spotifyUrl"),
            lastfmMBID=lastfm.get("mbid") if lastfm else None,
            imageUrl=image_url,
            relatedArtists=lastfm.get("similar", []) if lastfm else [],
            color=color,
            x=x,
            y=y,
            userTags=[],
            rank=rankScore
        )
        rankScore += 1
        merged.append(artist_node)

    # if write_to_file:
    #     with open(output_path, "w", encoding="utf-8") as f:
    #         json.dump([artist.to_dict() for artist in merged], f, indent=2)

    return merged


def implement_genre_data(artists: List[ArtistNode], top_artists: bool = False) -> List[ArtistNode]:
    with open(genre_map_path, "r", encoding="utf-8") as f:
        genre_map = json.load(f)

    finalized = []
    rankScore = 1

    for artist in artists:
        if artist.id is None or not artist.genres or artist.genres == []:
            continue
        else:
            artist.finalize_genres()

        # Choose color based on top genre
        top_genre = artist.genres[0]
        artist.color = genre_map.get(top_genre, {}).get("color", "#cccccc")


        x_total = 0
        y_total = 0
        weight_total = 0
        for idx, g in enumerate(artist.genres[:10]):
            g_data = genre_map.get(g)
            if g_data and "x" in g_data and "y" in g_data:
                weight = 1 / (idx + 1)
                x_total += g_data["x"] * weight
                y_total += g_data["y"] * weight
                weight_total += weight

        if weight_total:
            artist.x = x_total / weight_total
            artist.y = y_total / weight_total

        artist.rank = rankScore if top_artists else None
        rankScore += 1

        finalized.append(artist)

    return finalized
