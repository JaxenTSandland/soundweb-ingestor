from typing import Optional, Tuple
from neo4j import Session

def get_existing_artist_by_spotify_id(session: Session, spotify_id: str) -> Optional[Tuple[dict, list, bool]]:
    """
    Checks if an artist with the given Spotify ID exists in Neo4j.
    Returns:
        (artist_properties, userTags, isTopArtist) if found, else None
    """
    result = session.run(
        """
        MATCH (a:Artist {spotifyId: $spotifyId})
        RETURN a, a.userTags AS userTags, a:TopArtist AS isTopArtist
        """,
        {"spotifyId": spotify_id}
    )
    record = result.single()
    if record:
        return record["a"]._properties, record["userTags"] or [], record["isTopArtist"]
    return None