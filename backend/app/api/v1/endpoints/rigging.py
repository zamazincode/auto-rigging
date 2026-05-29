from fastapi import APIRouter, File, UploadFile, HTTPException
from fastapi.responses import FileResponse
from app.services.blender_service import BlenderService
from app.services.ml_service import MLService
from app.core.config import settings
import os
import shutil
import uuid

router = APIRouter()

ml_service = MLService(settings.KERAS_MODEL_PATH)

@router.post("/process", response_class=FileResponse)
async def process_model(file: UploadFile = File(...)):
    if not file.filename.endswith(('.obj', '.fbx', '.glb', '.gltf')):
        raise HTTPException(status_code=400, detail="Unsupported file format")

    task_id = str(uuid.uuid4())
    task_dir = os.path.abspath(os.path.join(settings.PUBLIC_DIR, task_id))
    os.makedirs(task_dir, exist_ok=True)
    
    input_path = os.path.join(task_dir, f"input_{file.filename}")
    renders_dir = os.path.join(task_dir, "renders")
    output_path = os.path.join(task_dir, "rigged_output.fbx")
    
    try:
        # 1. Save uploaded file
        with open(input_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # 2. Take Renders
        BlenderService.take_renders(input_path, renders_dir)
        
        # 3. Predict Category using ML
        ml_service.load_model()
        rig_type = ml_service.predict(renders_dir)
        print(f"Predicted rig type: {rig_type}")
        
        # 4. Run Rigging Pipeline
        BlenderService.run_auto_rig(input_path, rig_type, output_path)
        
        if not os.path.exists(output_path):
            raise Exception("Rigged output file was not generated.")
            
        return FileResponse(
            path=output_path, 
            media_type="application/octet-stream", 
            filename=f"rigged_{file.filename}.fbx"
        )
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
