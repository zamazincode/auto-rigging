import os

class Settings:
    PROJECT_NAME: str = "Auto-Rigging API"
    API_V1_STR: str = "/api/v1"
    BLENDER_PATH: str = os.getenv("BLENDER_PATH", r"C:\Program Files\Blender Foundation\Blender 5.0\blender.exe")
    TEMP_DIR: str = os.getenv("TEMP_DIR", "temp")
    PUBLIC_DIR: str = os.getenv("PUBLIC_DIR", "public")
    KERAS_MODEL_PATH: str = os.getenv(
        "KERAS_MODEL_PATH", 
        os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../ml_pipeline/saved_models/auto_rigger_efficientnet.keras"))
    )

settings = Settings()
