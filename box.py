from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from database import get_database
import pymysql
import datetime

box_route = APIRouter(prefix="/box", tags=["Box"])

class BoxUpdateModel(BaseModel):
    serial: str
    battery: int
    temperature: float
    status: str


class BoxLogModel(BaseModel):
    box_id: int
    event_type: str
    value: str | None = None
    lat: float | None = None
    lng: float | None = None


class AssignBoxModel(BaseModel):
    box_id: int
    delivery_id: int


# -----------------------------
# Atualizar estado da caixa
# -----------------------------

@box_route.post("/update")
async def update_box(data: BoxUpdateModel):
    db = get_database()
    cursor = db.cursor()

    try:
        cursor.execute("""
            UPDATE boxes
            SET battery_level=%s,
                temperature=%s,
                status=%s,
                last_seen=NOW()
            WHERE serial_number=%s
        """, (data.battery, data.temperature, data.status, data.serial))

        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Caixa não encontrada")

        db.commit()
        return {"message": "Box updated"}

    except pymysql.MySQLError:
        raise HTTPException(status_code=500, detail="Erro ao atualizar caixa")

    finally:
        cursor.close()
        db.close()


# -----------------------------
# Registar logs da caixa
# -----------------------------

@box_route.post("/log")
async def box_log(data: BoxLogModel):
    db = get_database()
    cursor = db.cursor()

    try:
        cursor.execute("""
            INSERT INTO box_logs (box_id, event_type, value, latitude, longitude, created_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
        """, (data.box_id, data.event_type, data.value, data.lat, data.lng))

        db.commit()
        return {"message": "Log registado"}

    except pymysql.MySQLError:
        raise HTTPException(status_code=500, detail="Erro ao registar log")

    finally:
        cursor.close()
        db.close()


# -----------------------------
# Atribuir caixa a uma entrega
# -----------------------------

@box_route.post("/assign")
async def assign_box(data: AssignBoxModel):
    db = get_database()
    cursor = db.cursor()

    try:
        cursor.execute("SELECT id FROM boxes WHERE id=%s", (data.box_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Caixa não encontrada")

        cursor.execute("SELECT id FROM deliveries WHERE id=%s", (data.delivery_id,))
        if cursor.fetchone() is None:
            raise HTTPException(status_code=404, detail="Entrega não encontrada")

        cursor.execute("""
            UPDATE deliveries SET box_id=%s WHERE id=%s
        """, (data.box_id, data.delivery_id))

        cursor.execute("""
            UPDATE boxes SET status='in_use' WHERE id=%s
        """, (data.box_id,))

        db.commit()
        return {"message": "Caixa atribuída à entrega"}

    except pymysql.MySQLError:
        raise HTTPException(status_code=500, detail="Erro ao atribuir caixa")

    finally:
        cursor.close()
        db.close()


# -----------------------------
# Obter estado da caixa
# -----------------------------

@box_route.get("/{box_id}")
async def get_box(box_id: int):
    db = get_database()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    try:
        cursor.execute("SELECT * FROM boxes WHERE id=%s", (box_id,))
        box = cursor.fetchone()

        if box is None:
            raise HTTPException(status_code=404, detail="Caixa não encontrada")

        return box

    except pymysql.MySQLError:
        raise HTTPException(status_code=500, detail="Erro ao obter caixa")

    finally:
        cursor.close()
        db.close()


# -----------------------------
# Obter logs da caixa
# -----------------------------

@box_route.get("/{box_id}/logs")
async def get_box_logs(box_id: int):
    db = get_database()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    try:
        cursor.execute("""
            SELECT * FROM box_logs
            WHERE box_id=%s
            ORDER BY created_at DESC
        """, (box_id,))

        logs = cursor.fetchall()
        return logs

    except pymysql.MySQLError:
        raise HTTPException(status_code=500, detail="Erro ao obter logs")

    finally:
        cursor.close()
        db.close()
