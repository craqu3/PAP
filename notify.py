from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from database import get_database
from auth_utils import get_current_user
from firebase_config import send_push_notification
import pymysql

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class RegisterDeviceModel(BaseModel):
    device_token: str
    platform: str = "android"  # android, ios, web


@router.post("/register")
def register_device(data: RegisterDeviceModel, user=Depends(get_current_user)):
    db = get_database()
    cursor = db.cursor()

    try:
        # Apagar tokens antigos do mesmo user (opcional)
        cursor.execute("DELETE FROM user_devices WHERE user_id=%s", (user["id"],))

        cursor.execute("""
            INSERT INTO user_devices (user_id, device_token, platform)
            VALUES (%s, %s, %s)
        """, (user["id"], data.device_token, data.platform))

        db.commit()
        return {"message": "Device registado com sucesso"}

    except pymysql.MySQLError:
        raise HTTPException(500, "Erro ao registar device")

    finally:
        cursor.close()
        db.close()


# -----------------------------
# Função interna para enviar notificação a um user
# -----------------------------
def notify_user(user_id: int, title: str, body: str, data: dict = None):
    db = get_database()
    cursor = db.cursor()

    try:
        cursor.execute("""
            SELECT device_token FROM user_devices
            WHERE user_id=%s
        """, (user_id,))

        tokens = cursor.fetchall()

        if not tokens:
            return {"status": "no_devices"}

        for (token,) in tokens:
            send_push_notification(token, title, body, data)

        return {"status": "sent"}

    finally:
        cursor.close()
        db.close()
