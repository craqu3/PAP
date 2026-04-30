from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from database import get_database
from auth_utils import get_current_user
import pymysql

router = APIRouter(prefix="/tracking", tags=["Tracking"])


class UpdateTrackingModel(BaseModel):
    delivery_id: int
    lat: float
    lng: float


@router.post("/update")
def update_tracking(data: UpdateTrackingModel, user=Depends(get_current_user)):
    if user["role"] != "deliver":
        raise HTTPException(403, "Apenas entregadores podem enviar localização")

    db = get_database()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    try:
        # Verificar se a entrega pertence ao entregador e está ativa
        cursor.execute("""
            SELECT d.id, d.status, o.client_delivery_lat, o.client_delivery_lng
            FROM deliveries d
            JOIN orders o ON d.order_id = o.id
            WHERE d.id=%s AND d.deliver_id=%s
        """, (data.delivery_id, user["id"]))

        delivery = cursor.fetchone()
        if not delivery:
            raise HTTPException(403, "Não tens acesso a esta entrega")

        if delivery["status"] not in ("in_progress", "assigned"):
            raise HTTPException(400, "Entrega não está ativa")

        # Inserir log de localização (tracking histórico)
        cursor.execute("""
            INSERT INTO delivery_tracking_logs (delivery_id, lat, lng)
            VALUES (%s, %s, %s)
        """, (data.delivery_id, data.lat, data.lng))

        db.commit()
        return {"message": "Localização registada"}

    except pymysql.MySQLError:
        raise HTTPException(500, "Erro ao registar localização")

    finally:
        cursor.close()
        db.close()


@router.get("/latest/{delivery_id}")
def get_latest_location(delivery_id: int, user=Depends(get_current_user)):
    db = get_database()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    try:
        # Obter entrega + pedido
        cursor.execute("""
            SELECT d.id, d.order_id, o.client_id, o.restaurant_id
            FROM deliveries d
            JOIN orders o ON d.order_id = o.id
            WHERE d.id=%s
        """, (delivery_id,))
        delivery = cursor.fetchone()

        if not delivery:
            raise HTTPException(404, "Entrega não encontrada")

        # Permissões
        if user["role"] == "client" and delivery["client_id"] != user["id"]:
            raise HTTPException(403, "Não tens acesso a esta entrega")

        if user["role"] == "restaurant" and delivery["restaurant_id"] != user["id"]:
            raise HTTPException(403, "Não tens acesso a esta entrega")

        if user["role"] not in ("client", "restaurant", "deliver"):
            raise HTTPException(403, "Sem permissão")

        # Última localização
        cursor.execute("""
            SELECT lat, lng, created_at
            FROM delivery_tracking_logs
            WHERE delivery_id=%s
            ORDER BY created_at DESC
            LIMIT 1
        """, (delivery_id,))

        loc = cursor.fetchone()
        if not loc:
            raise HTTPException(404, "Ainda não há localização para esta entrega")

        return loc

    finally:
        cursor.close()
        db.close()


@router.get("/path/{delivery_id}")
def get_delivery_path(delivery_id: int, user=Depends(get_current_user)):
    db = get_database()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    try:
        # Obter entrega + pedido
        cursor.execute("""
            SELECT d.id, d.order_id, o.client_id, o.restaurant_id
            FROM deliveries d
            JOIN orders o ON d.order_id = o.id
            WHERE d.id=%s
        """, (delivery_id,))
        delivery = cursor.fetchone()

        if not delivery:
            raise HTTPException(404, "Entrega não encontrada")

        # Permissões
        if user["role"] == "client" and delivery["client_id"] != user["id"]:
            raise HTTPException(403, "Não tens acesso a esta entrega")

        if user["role"] == "restaurant" and delivery["restaurant_id"] != user["id"]:
            raise HTTPException(403, "Não tens acesso a esta entrega")

        if user["role"] not in ("client", "restaurant", "deliver"):
            raise HTTPException(403, "Sem permissão")

        # Histórico completo
        cursor.execute("""
            SELECT lat, lng, created_at
            FROM delivery_tracking_logs
            WHERE delivery_id=%s
            ORDER BY created_at ASC
        """, (delivery_id,))

        path = cursor.fetchall()
        if not path:
            raise HTTPException(404, "Ainda não há localização para esta entrega")

        return path

    finally:
        cursor.close()
        db.close()
