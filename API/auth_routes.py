from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from database import get_database
from email_recover import send_recovery_email
from jwt import create_access_token
import bcrypt
import secrets
import datetime
import pymysql

auth_route = APIRouter(prefix="/auth", tags=["Auth"])

class RegisterRequest(BaseModel):
    firstName: str
    lastName: str
    email: str
    password: str
    role: str

class LoginRequest(BaseModel):
    email: str
    password: str

class RecoverPassword(BaseModel):
    email: str
class ResetPassword(BaseModel):
    email: str
    password: str
    token: str

@auth_route.post("/register")
async def register(request: RegisterRequest):
    db = get_database()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM users WHERE email = %s", (request.email,))
    user = cursor.fetchone()

    if user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email já foi registado")


    hashed_password = bcrypt.hashpw(request.password.encode("utf-8"), bcrypt.gensalt())
    hashed_password = hashed_password.decode("utf-8")
    try:
        cursor.execute("INSERT INTO users (firstName, lastName, email, password, role) VALUES (%s, %s, %s, %s, %s)",(request.firstName, request.lastName, request.email, hashed_password, request.role))
        print(f"Utilizador com o nome: {request.firstName} foi criado")
    except pymysql.MySQLError:
        raise HTTPException( status_code=500, detail="Erro ao criar utilizador" )
    
    return {"message": "Utilizador registado com sucesso"}

@auth_route.post("/recoverPassword")
async def recoverPassword(request: RecoverPassword, background: BackgroundTasks):
    db = get_database()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM users WHERE email = %s", (request.email,))
    user = cursor.fetchone()


    if user is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Não foi encontrado nenhum email correspondente")

    token = secrets.token_urlsafe(32)
    expire = datetime.datetime.now() + datetime.timedelta(minutes=10)

    try:
        cursor.execute("UPDATE users SET token = %s, tokenTime = %s WHERE email = %s",(token, expire, request.email))
        background.add_task(send_recovery_email, request.email, token, user["firstName"])
    except pymysql.MySQLError:
        raise HTTPException(status_code=500, detail="Erro ao criar os tokens de verificação")
    
    return {"message": "Email enviado com sucesso"}

@auth_route.post("/resetPassword")
async def resetPassword(request:ResetPassword):
    db = get_database()
    cursor = db.cursor()


    cursor.execute("SELECT * FROM users WHERE email = %s", (request.email,))
    user = cursor.fetchone()

    if user == None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Não foi possível encontrar o email na base de dados")
    
    if user["token"] != request.token: 
        raise HTTPException(status_code=400, detail="Token inválido")

    token_time = datetime.datetime.fromisoformat(str(user["tokenTime"]))

    if token_time < datetime.datetime.now():
        raise HTTPException(status_code=400, detail="Token expirado")
    
    password = bcrypt.hashpw( request.password.encode("utf-8"), bcrypt.gensalt() ).decode("utf-8")
    cursor.execute( "UPDATE users SET password = %s, token = NULL, tokenTime = NULL WHERE ID = %s", (password, user["ID"]) )

    return{"message": "Password alterada com sucesso"}

@auth_route.post("/login")
async def login(request: LoginRequest):
    db = get_database()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM users WHERE email = %s", (request.email,))
    user = cursor.fetchone()

    if user is None:
        raise HTTPException(status_code=400, detail="Credenciais Inválidas")

    if not bcrypt.checkpw(request.password.encode("utf-8"), user["password"].encode("utf-8")):
        raise HTTPException(status_code=400, detail="Credenciais Inválidas")


    access_token = create_access_token({"sub": str(user["ID"]), "email": user["email"], "role": user["role"]})

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }



