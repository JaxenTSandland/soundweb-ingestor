from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

@dataclass
class IncompleteArtist:
    spotify_id: str
    user_tag: str
    name: str = ""
    popularity: int = 0
    image_url: str = ""
    failure_reason: str = "unknown"
    last_attempted: datetime = datetime.now(tz=timezone.utc)

    def to_sql_tuple(self):
        return (
            self.spotify_id,
            self.user_tag,
            self.name,
            self.popularity,
            self.image_url,
            self.failure_reason,
            self.last_attempted
        )
