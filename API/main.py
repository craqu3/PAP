import auth_routes

import jwt
import mysql.connector
from fastapi import FastAPI




mydb = mysql.connector.connect(
  host=" ",
  user=" ",
  password=" "
)



cursor = mydb
cursor.execute("SHOW DATABASE")


app = FastAPI()


app.includeroutes()


@app.get("/")
def teste():
    return {"API": "A minha API está a funcionar!"}



