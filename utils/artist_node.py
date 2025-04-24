from typing import List, Optional
from dataclasses import dataclass, asdict

@dataclass
class ArtistNode:
    id: str
    name: str
    popularity: int = 0
    spotifyId: Optional[str] = None
    spotifyUrl: Optional[str] = None
    lastfmMBID: Optional[str] = None
    imageUrl: Optional[str] = None
    genres: List[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    color: Optional[str] = None
    userTags: Optional[List[str]] = None
    relatedArtists: Optional[List[str]] = None

    def to_dict(self):
        return asdict(self)