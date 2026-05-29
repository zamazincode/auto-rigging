import subprocess
import os
from app.core.config import settings

class BlenderService:
    @staticmethod
    def take_renders(input_model: str, output_dir: str):
        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../blender_scripts/tools/take_renders.py"))
        
        cmd = [
            settings.BLENDER_PATH,
            "--background",
            "--python", script_path,
            "--",
            "--input", input_model,
            "--output", output_dir
        ]
        
        print(f"Running Blender render: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        
        if result.returncode != 0:
            print("Blender Render Output:", result.stdout)
            print("Blender Render Error:", result.stderr)
            raise Exception("Failed to take renders with Blender.")
            
    @staticmethod
    def run_auto_rig(input_model: str, rig_type: str, output_model: str):
        script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../blender_scripts/tools/run_rigging.py"))
        
        if not os.path.exists(script_path):
             raise Exception(f"Rigging wrapper script not found: {script_path}")
             
        cmd = [
            settings.BLENDER_PATH,
            "--background",
            "--python", script_path,
            "--",
            "--input", input_model,
            "--output", output_model,
            "--type", rig_type
        ]
        
        print(f"Running Blender auto-rig ({rig_type}): {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        
        log_path = os.path.join(os.path.dirname(output_model), "blender_rigging_log.txt")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("--- BLENDER RIGGING STDOUT ---\n")
            f.write(result.stdout)
            f.write("\n--- BLENDER RIGGING STDERR ---\n")
            f.write(result.stderr)
            
        if result.returncode != 0:
            raise Exception(f"Failed to run auto-rig for {rig_type}. See log: {log_path}")
