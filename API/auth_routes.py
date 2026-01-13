from fastapi import APIRouter
import main
auth_route = APIRouter(prefix="/auth", tags=["Auth"])




@auth_route.post("/register")
async def register(email: str, password: str):
    if user != users:

    else:

    return




@auth_route.post("/login")
def login(request: LoginRequest):
    return {"email": request.email, "password": request.password}



