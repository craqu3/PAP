from dotenv import load_dotenv
from fastapi import FastAPI


from auth_routes import auth_route
from routes import settings_route
from video import video_route
from box import box_route


app = FastAPI()

load_dotenv()



app.include_router(auth_route)
app.include_router(settings_route)
app.include_router(video_route)
app.include_router(box_route)

@app.get("/")
async def teste():
    return {"API": "A minha API está a funcionar!"}



