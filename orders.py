from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from database import get_database
from auth_utils import get_current_user
import pymysql

router = APIRouter(prefix="/orders", tags=["Orders"])


# -----------------------------
# MODELOS
# -----------------------------
class CreateOrderModel(BaseModel):
    restaurant_id: int
    client_id: int
    items: str
    price: float

class UpdateOrderStatusModel(BaseModel):
    order_id: int
    status: str


# -----------------------------
# CRIAR PEDIDO
# -----------------------------
@router.post("/create")
def create_order(data: CreateOrderModel, user=Depends(get_current_user)):
    if user["role"] != "restaurant":
        raise HTTPException(403, "Apenas restaurantes podem criar pedidos")

    db = get_database()
    cursor = db.cursor()

    try:
        # Verificar se cliente existe
        cursor.execute("SELECT id FROM users WHERE id=%s AND role='client'", (data.client_id,))
        if cursor.fetchone() is None:
            raise HTTPException(404, "Cliente não encontrado")

        # Criar pedido
        cursor.execute("""
            INSERT INTO orders (restaurant_id, client_id, items, price, status, created_at)
            VALUES (%s, %s, %s, %s, 'pending', NOW())
        """, (data.restaurant_id, data.client_id, data.items, data.price))

        db.commit()
        return {"message": "Pedido criado com sucesso"}

    except pymysql.MySQLError:
        raise HTTPException(500, "Erro ao criar pedido")

    finally:
        cursor.close()
        db.close()


# -----------------------------
# ATUALIZAR ESTADO DO PEDIDO
# -----------------------------
@router.put("/status")
def update_order_status(data: UpdateOrderStatusModel, user=Depends(get_current_user)):
    if user["role"] != "restaurant":
        raise HTTPException(403, "Apenas restaurantes podem atualizar pedidos")

    valid_states = ["pending", "preparing", "ready", "cancelled", "delivered"]

    if data.status not in valid_states:
        raise HTTPException(400, "Estado inválido")

    db = get_database()
    cursor = db.cursor()

    try:
        cursor.execute("SELECT id FROM orders WHERE id=%s", (data.order_id,))
        if cursor.fetchone() is None:
            raise HTTPException(404, "Pedido não encontrado")

        cursor.execute("""
            UPDATE orders SET status=%s, updated_at=NOW()
            WHERE id=%s
        """, (data.status, data.order_id))

        db.commit()
        return {"message": "Estado atualizado com sucesso"}

    except pymysql.MySQLError:
        raise HTTPException(500, "Erro ao atualizar estado")

    finally:
        cursor.close()
        db.close()


# -----------------------------
# LISTAR PEDIDOS DO RESTAURANTE
# -----------------------------
@router.get("/restaurant")
def get_restaurant_orders(user=Depends(get_current_user)):
    if user["role"] != "restaurant":
        raise HTTPException(403, "Apenas restaurantes podem ver pedidos")

    db = get_database()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT * FROM orders
        WHERE restaurant_id=%s
        ORDER BY created_at DESC
    """, (user["id"],))

    orders = cursor.fetchall()

    cursor.close()
    db.close()

    return orders


# -----------------------------
# LISTAR PEDIDOS DO CLIENTE
# -----------------------------
@router.get("/client")
def get_client_orders(user=Depends(get_current_user)):
    if user["role"] != "client":
        raise HTTPException(403, "Apenas clientes podem ver os seus pedidos")

    db = get_database()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT * FROM orders
        WHERE client_id=%s
        ORDER BY created_at DESC
    """, (user["id"],))

    orders = cursor.fetchall()

    cursor.close()
    db.close()

    return orders


# -----------------------------
# OBTER PEDIDO POR ID
# -----------------------------
@router.get("/{order_id}")
def get_order(order_id: int, user=Depends(get_current_user)):
    db = get_database()
    cursor = db.cursor(pymysql.cursors.DictCursor)

    cursor.execute("SELECT * FROM orders WHERE id=%s", (order_id,))
    order = cursor.fetchone()

    if not order:
        raise HTTPException(404, "Pedido não encontrado")

    # Segurança
    if user["role"] == "client" and order["client_id"] != user["id"]:
        raise HTTPException(403, "Não tens acesso a este pedido")

    if user["role"] == "restaurant" and order["restaurant_id"] != user["id"]:
        raise HTTPException(403, "Não tens acesso a este pedido")

    cursor.close()
    db.close()

    return order
