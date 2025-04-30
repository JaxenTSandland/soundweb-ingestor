import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from main import generate_custom_artist_data

app = FastAPI()

@app.get("/api/test")
def api_test():
    return {"success": True, "message": "Ingestor API is running."}

class CustomArtistRequest(BaseModel):
    user_tag: str
    name: str
    spotify_id: str

@app.post("/api/add-custom-artist")
def ingest_custom_artist(request: CustomArtistRequest):
    try:
        result = generate_custom_artist_data(
            user_tag=request.user_tag,
            name=request.name,
            spotify_id=request.spotify_id
        )
        return {"success": True, "message": f"Custom artist {result.data.artistNode.name} ingested successfully.", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))