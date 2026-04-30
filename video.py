from fastapi import APIRouter, UploadFile, File
import os

video_route = APIRouter()

VIDEOS_DIR = "videos"
os.makedirs(VIDEOS_DIR, exist_ok=True)


@video_route.post("/video/upload")
async def upload_video(user_id: int, file: UploadFile = File(...)):
    path = os.path.join(VIDEOS_DIR, f"{user_id}_{file.filename}")

    content = await file.read()

    with open(path, "wb") as f:
        f.write(content)

    return {
        "message": "ok",
        "file": path
    }