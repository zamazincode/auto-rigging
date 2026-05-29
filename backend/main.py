from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.api import api_router
from app.core.config import settings

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_STR)

from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
import os

# Create public directory if it doesn't exist
os.makedirs(settings.PUBLIC_DIR, exist_ok=True)

# Mount public directory for static file serving
app.mount("/public", StaticFiles(directory=settings.PUBLIC_DIR), name="public")

# ==========================================
# ENDPOINTS
# ==========================================
# 1. GET /
#    Ana dizine istek atıldığında otomatik olarak Swagger UI (/docs) arayüzüne yönlendirir.
#
# 2. POST /api/v1/rigging/process
#    Frontend üzerinden gelen 3D modelleri kabul eder.
#    - Modelin Blender üzerinden renderlarını alır.
#    - Keras AI modeli ile (humanoid/quadruped) sınıflandırmasını yapar.
#    - İlgili Blender otomatik rig scriptini çalıştırır.
#    - Riglenmiş .fbx dosyasını döndürür.
# ==========================================

@app.get("/")
def root():
    return RedirectResponse(url="/docs")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="localhost", port=8000, reload=True)
