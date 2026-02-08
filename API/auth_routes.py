from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel
from database import get_database
from email import send_recovery_email
import bcrypt
import secrets
import datetime

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
    first_name: str
    email: str
class ResetPassword(BaseModel):
    email: str
    new_password: str

@auth_route.post("/register")
async def register(request: RegisterRequest):
    db = get_database()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM users WHERE email = %s", (request.email))
    user = cursor.fetchone()

    if user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email já foi registado")


    hashed_password = bcrypt.hashpw(request.password.encode("utf-8"), bcrypt.gensalt())
    hashed_password = hashed_password.decode("utf-8")
    try:
        cursor.execute("INSERT INTO users (firstName, lastName, email, password, role) VALUES (%s, %s, %s, %s, %s)",(request.firstName, request.lastName, request.email, hashed_password, request.role))
        print(f"Utilizador com o nome: {request.firstName} foi criado")
    except pymysql.MySQL.Error:
        raise HTTPException( status_code=500, detail="Erro ao criar utilizador" )
    
    return {"message": "Utilizador registado com sucesso"}

@auth_route.post("/recoverPassword")
async def recoverPassword(request: RecoverPassword):
    db = get_database()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM users WHERE email = %s", (request.email))
    user = cursor.fetchone()


    if user != None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Não foi encontrado nenhum email correspondente")

    token = secrets.token_urlsafe(32)
    expire = datetime.datetime.now() + datetime.timedelta(minutes=10)

    try:
        cursor.execute("UPDATE users SET reset_token = %s, reset_token_expire = %s WHERE email = %s",(token, expire, request.email))
        BackgroundTasks.add_task( send_recovery_email, request.email, token, user["first_name"])
    except pymysql.Mysql.Error:
        raise HTTPException(status_code=500, detail="Erro ao criar os tokens de verificação")


@auth_route.post("/resetPassword")
async def resetPassword(request:ResetPassword):
    db = get_database()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM users WHERE email = %s", (request.email))
    user = cursor.fetchone()

    if user != None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Não foi encontrado o email na base de dados")

    if user["tokenTime"] is None or user["tokenTime"] < datetime.datetime.now():
        raise HTTPException(status_code=400, detail="Token expirado")
    
    password = bcrypt.hashpw( request.new_password.encode("utf-8"), bcrypt.gensalt() ).decode("utf-8")
    cursor.execute( "UPDATE users SET password = %s, token = NULL, tokenTime = NULL WHERE id = %s", (password, user["id"]) )


@auth_route.post("/login")
async def login(request: LoginRequest):
    db = get_database()
    cursor = db.cursor()

    cursor.execute("SELECT * FROM users WHERE email = %s", (request.email,))
    user = cursor.fetchone()





    access_token = create_access_token({"sub": str(user["id"]), "email": user["email"], "role": user["role"]})

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }



