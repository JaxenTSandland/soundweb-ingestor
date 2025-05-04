import json
import os
from typing import List, Optional, ClassVar
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone

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
    rank: Optional[int] = None
    lastUpdated: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    genre_map: ClassVar[dict] = {}
    genre_map_path: ClassVar[Optional[str]] = "../data/genreMap.json"

    @classmethod
    def load_genre_map(cls, path: Optional[str] = None):
        if path:
            cls.genre_map_path = path
        if not cls.genre_map_path:
            raise ValueError("Genre map path must be set before loading.")

        base_dir = os.path.dirname(__file__)
        absolute_path = os.path.abspath(os.path.join(base_dir, cls.genre_map_path))

        with open(absolute_path, "r", encoding="utf-8") as f:
            cls.genre_map = json.load(f)

    def append_genres(self, genres):
        if self.genres is None:
            self.genres = []

        if not self.genre_map:
            self.load_genre_map()

        cleaned = []
        for genre in genres:
            if isinstance(genre, dict):
                name = genre.get("name", "").lower()
            elif isinstance(genre, str):
                name = genre.lower()
            else:
                continue

            if name and name in self.genre_map:
                cleaned.append(name)

        self.genres += cleaned

    def finalize_genres(self):
        if not self.genres:
            return

        frequency = {}
        for genre in self.genres:
            frequency[genre] = frequency.get(genre, 0) + 1

        seen = set()
        unique_genres = [g for g in self.genres if not (g in seen or seen.add(g))]

        unique_genres.sort(
            key=lambda g: frequency[g],
            reverse=True
        )

        self.genres = unique_genres

    def to_dict(self):
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)
