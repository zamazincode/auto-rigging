from fastapi import APIRouter
from app.api.v1.endpoints import rigging

api_router = APIRouter()
api_router.include_router(rigging.router, prefix="/rigging", tags=["rigging"])
