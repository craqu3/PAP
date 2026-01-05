from fastapi import APIRouter

auth_route = APIRouter(prefix="/auth", tags=["Auth"])







@auth_route.post("/login")
def login(request: LoginRequest):
    return {"email": request.email, "password": request.password}



@auth_route.post("/register")
def login(request: RegisterRequest):
    return {"email": request.email, "password": request.password}