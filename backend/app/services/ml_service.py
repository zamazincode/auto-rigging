import os
import numpy as np
from PIL import Image
import tensorflow as tf
from tensorflow.keras.preprocessing import image

# === KERAS BUG "MONKEY PATCH" ===
original_dense_init = tf.keras.layers.Dense.__init__

def patched_dense_init(self, *args, **kwargs):
    kwargs.pop('quantization_config', None) 
    original_dense_init(self, *args, **kwargs)

tf.keras.layers.Dense.__init__ = patched_dense_init
# ================================

class MLService:
    def __init__(self, model_path: str):
        self.model_path = model_path
        self.model = None
        self.classes = ['humanoid', 'quadruped']
        
    def load_model(self):
        if self.model is None:
            print(f"Loading Keras model from {self.model_path}")
            if os.path.exists(self.model_path):
                self.model = tf.keras.models.load_model(self.model_path)
            else:
                print(f"WARNING: Model file not found at {self.model_path}. ML inference will be mocked.")
    
    def predict(self, renders_dir: str) -> str:
        """
        Reads 4 render images from the directory, processes them, and predicts the class.
        Returns 'humanoid' or 'quadruped'.
        """
        if self.model is None:
            return "humanoid"  # Mock default if model not loaded
            
        images = []
        for i in range(4):
            img_path = os.path.join(renders_dir, f"render_{i}.png")
            if os.path.exists(img_path):
                img = image.load_img(img_path, target_size=(256, 256))
                img_array = image.img_to_array(img)
                images.append(img_array)
                
        if not images:
            raise ValueError("No render images found for prediction.")
            
        batch = np.array(images)
        predictions = self.model.predict(batch)
        
        avg_pred = np.mean(predictions, axis=0)
        predicted_class_idx = np.argmax(avg_pred)
        
        return self.classes[predicted_class_idx]
