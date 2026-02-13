from database import get_database
from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
import pymysql


db = get_database()
cursor = db.cursor()

settings_route = APIRouter(prefix="/settings", tags=["Settings"])




@settings_route.get("/MyAcount")
def informations(email:str):


    

    try:
        cursor.execute("SELECT * FROM users WHERE email = %s",(email,))
        user = cursor.fetchone()
    except email is None:
        raise HTTPException(status_code=500, detail="Email inválido")
    except pymysql.Mysql.Error:
        raise HTTPException(status_code=500, detail="Erro ao acessar a DataBase")
    except user is None:
        raise HTTPException(status_code=500, detail="Erro ao conseguir as informações")
    return user