from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer
import jwt
from database import get_database
import pymysql
from dotenv import load_dotenv 
import os 
load_dotenv()

security = HTTPBearer()
SECRET = os.getenv("SECRET_KEY")  # coloca no .env

def get_current_user(credentials=Depends(security)):
    token = credentials.credentials

    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token inválido")

    user_id = payload.get("id")
    if not user_id:
        raise HTTPException(401, "Token inválido")

    db = get_database()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    cursor.execute("SELECT id, email, role FROM users WHERE id=%s", (user_id,))
    user = cursor.fetchone()

    cursor.close()
    db.close()

    if not user:
        raise HTTPException(401, "Utilizador não encontrado")

    return user


def require_role(*allowed_roles):
    def wrapper(user=Depends(get_current_user)):
        if user["role"] not in allowed_roles:
            raise HTTPException(403, "Sem permissão")
        return user
    return wrapper
