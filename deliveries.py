from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from database import get_database
from auth_utils import get_current_user, require_role
from notify import notify_user
import pymysql

router = APIRouter(prefix="/deliveries", tags=["Deliveries"])


# -----------------------------
# MODELOS
# -----------------------------
class AssignDeliveryModel(BaseModel):
    order_id: int
    deliver_id: int


class StartDeliveryModel(BaseModel):
    delivery_id: int


class FinishDeliveryModel(BaseModel):
    delivery_id: int


# -----------------------------
# ATRIBUIR ENTREGA (RESTAURANTE)
# -----------------------------
@router.post("/assign", dependencies=[Depends(require_role("restaurant"))])
def assign_delivery(data: AssignDeliveryModel, user=Depends(get_current_user)):
    if user["role"] != "restaurant":
        raise HTTPException(403, "Apenas restaurantes podem atribuir entregas")

    db = get_database()
    cursor = db.cursor()

    try:
        # Buscar dados do pedido
        cursor.execute("""
            SELECT client_id, restaurant_id 
            FROM orders 
            WHERE id=%s
        """, (data.order_id,))
        order = cursor.fetchone()

        if not order:
            raise HTTPException(404, "Pedido não encontrado")

        client_id, restaurant_id = order

        if restaurant_id != user["id"]:
            raise HTTPException(403, "Não tens permissão para este pedido")

        # Verificar entregador
        cursor.execute("""
            SELECT id FROM users 
            WHERE id=%s AND role='deliver'
        """, (data.deliver_id,))
        if cursor.fetchone() is None:
            raise HTTPException(404, "Entregador não encontrado")

        # Criar entrega otimizada
        cursor.execute("""
            INSERT INTO deliveries (order_id, deliver_id, client_id, restaurant_id, status)
            VALUES (%s, %s, %s, %s, 'assigned')
        """, (data.order_id, data.deliver_id, client_id, restaurant_id))

        # Notificação para o entregador
        notify_user(
            data.deliver_id,
            "Nova entrega atribuída",
            "Tens uma nova entrega para recolher."
        )

        db.commit()
        return {"message": "Entrega atribuída com sucesso"}

    except pymysql.MySQLError:
        raise HTTPException(500, "Erro ao atribuir entrega")

    finally:
        cursor.close()
        db.close()


# -----------------------------
# ENTREGADOR VÊ ENTREGA ATUAL
# -----------------------------
@router.get("/active", dependencies=[Depends(require_role("deliver"))])
def get_active_delivery(user=Depends(get_current_user)):
    if user["role"] != "deliver":
        raise HTTPException(403, "Apenas entregadores podem ver entregas ativas")

    db = get_database()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT d.*, o.items, o.price
        FROM deliveries d
        JOIN orders o ON d.order_id = o.id
        WHERE d.deliver_id=%s AND d.status IN ('assigned', 'in_progress')
    """, (user["id"],))

    delivery = cursor.fetchone()

    cursor.close()
    db.close()

    if not delivery:
        return {"active": False}

    return {"active": True, "delivery": delivery}


# -----------------------------
# ENTREGADOR INICIA ENTREGA
# -----------------------------
@router.put("/start", dependencies=[Depends(require_role("deliver"))])
def start_delivery(data: StartDeliveryModel, user=Depends(get_current_user)):
    if user["role"] != "deliver":
        raise HTTPException(403, "Apenas entregadores podem iniciar entregas")

    db = get_database()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    try:
        cursor.execute("""
            SELECT deliver_id, status, client_id
            FROM deliveries
            WHERE id=%s
        """, (data.delivery_id,))
        delivery = cursor.fetchone()

        if not delivery:
            raise HTTPException(404, "Entrega não encontrada")

        if delivery["deliver_id"] != user["id"]:
            raise HTTPException(403, "Não tens permissão para esta entrega")

        if delivery["status"] != "assigned":
            raise HTTPException(400, "Entrega já foi iniciada ou concluída")

        cursor.execute("""
            UPDATE deliveries
            SET status='in_progress', started_at=NOW()
            WHERE id=%s
        """, (data.delivery_id,))

        # Notificar cliente
        notify_user(
            delivery["client_id"],
            "A sua entrega está a caminho",
            "O entregador iniciou a entrega."
        )

        db.commit()
        return {"message": "Entrega iniciada"}

    except pymysql.MySQLError:
        raise HTTPException(500, "Erro ao iniciar entrega")

    finally:
        cursor.close()
        db.close()


# -----------------------------
# ENTREGADOR TERMINA ENTREGA
# -----------------------------
@router.put("/finish", dependencies=[Depends(require_role("deliver"))])
def finish_delivery(data: FinishDeliveryModel, user=Depends(get_current_user)):
    if user["role"] != "deliver":
        raise HTTPException(403, "Apenas entregadores podem terminar entregas")

    db = get_database()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    try:
        cursor.execute("""
            SELECT deliver_id, status, restaurant_id
            FROM deliveries
            WHERE id=%s
        """, (data.delivery_id,))
        delivery = cursor.fetchone()

        if not delivery:
            raise HTTPException(404, "Entrega não encontrada")

        if delivery["deliver_id"] != user["id"]:
            raise HTTPException(403, "Não tens permissão para esta entrega")

        if delivery["status"] != "in_progress":
            raise HTTPException(400, "Entrega não está em progresso")

        cursor.execute("""
            UPDATE deliveries
            SET status='delivered', finished_at=NOW()
            WHERE id=%s
        """, (data.delivery_id,))

        notify_user(delivery["restaurant_id"],"Entrega concluída","O pedido foi entregue ao cliente.")
        notify_user(delivery["deliver_id"],"Entrega concluída","O pedido do cliente foi entregue com sucesso.")
        notify_user(delivery["client_id"],"Entrega concluída","O seu pedido foi entregue.")

        db.commit()
        return {"message": "Entrega concluída"}

    except pymysql.MySQLError:
        raise HTTPException(500, "Erro ao terminar entrega")

    finally:
        cursor.close()
        db.close()


# -----------------------------
# CLIENTE ACOMPANHA ENTREGA
# -----------------------------
@router.get("/track/{order_id}", dependencies=[Depends(require_role("client, restaurant"))])
def track_delivery(order_id: int, user=Depends(get_current_user)):
    if user["role"] != "client" or "restaurant":
        raise HTTPException(403, "Apenas clientes podem acompanhar entregas")

    db = get_database()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT d.*, o.items, o.price
        FROM deliveries d
        JOIN orders o ON d.order_id = o.id
        WHERE d.order_id=%s AND d.client_id=%s
    """, (order_id, user["id"]))

    delivery = cursor.fetchone()

    cursor.close()
    db.close()

    if not delivery:
        raise HTTPException(404, "Entrega não encontrada")

    return delivery
