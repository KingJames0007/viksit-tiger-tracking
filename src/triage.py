import os
from PytorchWildlife.models import detection as pw_detection

print("Loading MegaDetector V6 into server memory...")
# Initialize model globally so it doesn't reload on every API request
model = pw_detection.MegaDetectorV6(version="MDV6-yolov10-e")

def process_triage(file_path, confidence_threshold=0.40):
    """
    Runs MegaDetector on a single image. 
    Returns True if an animal is detected, False otherwise.
    """
    results = model.single_image_detection(file_path)
    
    if 'detections' in results:
        detections = results['detections']
        
        for i in range(len(detections)):
            class_id = detections.class_id[i]
            conf = detections.confidence[i]
            
            # MegaDetector V6 Classes: 0 = animal, 1 = person, 2 = vehicle
            if class_id == 0 and conf >= confidence_threshold:
                return True # Animal detected
                
    return False # Blank image