import jwt
import mysql.connector
from fastapi import FastAPI


app = FastAPI()

def get_connection():
    return mysql.connector.connect(
        host=" ",
        user=" ",
        password=" ",
        database=""
    )





@app.get("/")
def teste():
    return {"API": "A minha API está a funcionar!"}



@app.post("/login")
def login(request: LoginRequest):
    return {"email": request.email, "password": request.password}