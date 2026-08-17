import os
from PytorchWildlife.models import detection as pw_detection

print("Loading MegaDetector V6 into server memory...")
# Initialize model globally so it doesn't reload on every API request
model = pw_detection.MegaDetectorV6(version="MDV6-yolov10-e")

def process_triage(file_path, confidence_threshold=0.40):
    """
    Runs MegaDetector on a single image. 
    Returns (has_animal, bbox)
    - has_animal: True if an animal is detected, False otherwise.
    - bbox: [x_min, y_min, x_max, y_max] in pixels for the highest-confidence animal, or None.
    """
    results = model.single_image_detection(file_path)
    
    best_box = None
    best_conf = -1.0
    
    if 'detections' in results:
        detections = results['detections']
        
        for i in range(len(detections)):
            class_id = detections.class_id[i]
            conf = detections.confidence[i]
            
            # MegaDetector V6 Classes: 0 = animal, 1 = person, 2 = vehicle
            if class_id == 0 and conf >= confidence_threshold:
                if conf > best_conf:
                    best_conf = conf
                    best_box = [
                        int(detections.xyxy[i][0]),
                        int(detections.xyxy[i][1]),
                        int(detections.xyxy[i][2]),
                        int(detections.xyxy[i][3])
                    ]
                    
    if best_box is not None:
        return True, best_box
    return False, None