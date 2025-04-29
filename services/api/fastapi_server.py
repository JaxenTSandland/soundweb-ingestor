from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../")))

from main import generate_custom_artist_data

app = FastAPI()

class CustomArtistRequest(BaseModel):
    name: str
    spotify_id: str

@app.get("/api/test")
def api_test():
    return {"success": True, "message": f"Ingestor API is running."}

@app.post("/api/add/custom-artist")
def ingest_custom_artist(request: CustomArtistRequest):
    try:
        result = generate_custom_artist_data(
            name=request.name,
            spotify_id=request.spotify_id
        )
        return {"success": True, "message": f"Custom artist {request.name} ingested successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("fastapi_server:app", host="0.0.0.0", port=8000, reload=True)