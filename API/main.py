from fastapi import FastAPI
from auth_routes import auth_route




app = FastAPI()


app.include_router(auth_route)


@app.get("/")
async def teste():
    return {"API": "A minha API está a funcionar!"}



