from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from database import get_database
import bcrypt
from auth_utils import get_current_user

settings_route = APIRouter(prefix="/settings", tags=["Settings"])


# MODELOS CORRETOS (sem user_id)
class UpdateName(BaseModel):
    firstName: str
    lastName: str

class UpdateEmail(BaseModel):
    email: EmailStr

class UpdatePassword(BaseModel):
    password: str

class UpdateTheme(BaseModel):
    theme: str

class UpdateNotifications(BaseModel):
    notifications: bool




# -----------------------------
# Atualizar nome
# -----------------------------
@settings_route.put("/name")
def update_name(settings: UpdateName, user=Depends(get_current_user)):
    db = get_database()
    cursor = db.cursor()

    cursor.execute(
        "UPDATE users SET firstName=%s, lastName=%s WHERE id=%s",
        (settings.firstName, settings.lastName, user["id"])
    )

    return {"message": "Nome atualizado com sucesso"}


# -----------------------------
# Atualizar email
# -----------------------------
@settings_route.put("/email")
def update_email(settings: UpdateEmail, user=Depends(get_current_user)):
    db = get_database()
    cursor = db.cursor()

    cursor.execute(
        "SELECT id FROM users WHERE email=%s AND id!=%s",
        (settings.email, user["id"])
    )
    if cursor.fetchone():
        raise HTTPException(status_code=400, detail="Email já está em uso")

    cursor.execute(
        "UPDATE users SET email=%s WHERE id=%s",
        (settings.email, user["id"])
    )

    return {"message": "Email atualizado com sucesso"}


# -----------------------------
# Atualizar password
# -----------------------------
@settings_route.put("/password")
def update_password(settings: UpdatePassword, user=Depends(get_current_user)):
    db = get_database()
    cursor = db.cursor()

    if len(settings.password) < 8:
        raise HTTPException(status_code=400, detail="Password deve ter pelo menos 8 caracteres")

    hashed = bcrypt.hashpw(settings.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    cursor.execute(
        "UPDATE users SET password=%s WHERE id=%s",
        (hashed, user["id"])
    )

    return {"message": "Password atualizada com sucesso"}


# -----------------------------
# Atualizar tema
# -----------------------------
@settings_route.put("/theme")
def update_theme(settings: UpdateTheme, user=Depends(get_current_user)):
    db = get_database()
    cursor = db.cursor()

    cursor.execute(
        "UPDATE users SET theme=%s WHERE id=%s",
        (settings.theme, user["id"])
    )

    return {"message": "Tema atualizado com sucesso"}


@settings_route.get("/me")
def get_profile(user=Depends(get_current_user)):
    db = get_database()
    cursor = db.cursor()

    cursor.execute(
        "SELECT firstName, lastName, email, theme, notifications FROM users WHERE id=%s",
        (user["id"],)
    )

    profile = cursor.fetchone()

    if not profile:
        raise HTTPException(status_code=404, detail="Utilizador não encontrado")

    return {
        "firstName": profile[0],
        "lastName": profile[1],
        "email": profile[2],
        "theme": profile[3],
        "notifications": profile[4]
    }

# -----------------------------
# Atualizar notificações
# -----------------------------
@settings_route.put("/notifications")
def update_notifications(settings: UpdateNotifications, user=Depends(get_current_user)):
    db = get_database()
    cursor = db.cursor()

    cursor.execute(
        "UPDATE users SET notifications=%s WHERE id=%s",
        (settings.notifications, user["id"])
    )

    return {"message": "Notificações atualizadas com sucesso"}
