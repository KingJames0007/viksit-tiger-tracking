import os
import time
import shutil
# PytorchWildlife is the official wrapper for MegaDetector V6
from PytorchWildlife.models import detection as pw_detection

print("Downloading and loading MegaDetector V6 (this may take a moment on the first run)...")
# MDV6-yolov10-e provides the best balance of speed and accuracy for a local machine
model = pw_detection.MegaDetectorV6(version="MDV6-yolov10-e") 

# Using raw string literals (r"") for Windows paths
raw_dir = r"data\raw"
quarantine_dir = r"data\quarantine"
# 85% is a strict threshold; you can lower this to 0.40 if it misses tigers in poor lighting
confidence_threshold = 0.4 

start_time = time.time()
bytes_saved = 0
images_moved = 0

# Ensure directories exist before running
os.makedirs(raw_dir, exist_ok=True)
os.makedirs(quarantine_dir, exist_ok=True)

for filename in os.listdir(raw_dir):
    if not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff')):
        continue
        
    file_path = os.path.join(raw_dir, filename)
    
    # Run the image through the model
    results = model.single_image_detection(file_path)
    
    has_animal = False
    
    # Parse the detection results. MegaDetector classifies animals as category '1' or 'animal'.
    # Parse the detection results. MegaDetector V6 returns an sv.Detections object
    # Parse the detection results using strict class IDs
    if 'detections' in results:
        detections = results['detections']
        
        # Iterate through the detections
        for i in range(len(detections)):
            class_id = detections.class_id[i]
            conf = detections.confidence[i]
            
            if class_id == 0:
                print(f"--> Found animal with {conf*100:.1f}% confidence")
            
            # MegaDetector V6 Classes: 0 = animal, 1 = person, 2 = vehicle
            if class_id == 0 and conf >= confidence_threshold:
                has_animal = True
                break
                
    # If no animal is found above the threshold, move the file to quarantine
    if not has_animal:
        file_size = os.path.getsize(file_path)
        bytes_saved += file_size
        images_moved += 1
        
        destination = os.path.join(quarantine_dir, filename)
        shutil.move(file_path, destination)
        print(f"Moved to quarantine: {filename}")

elapsed_time = time.time() - start_time
mb_saved = bytes_saved / (1024 * 1024)

print("-" * 30)
print("Triage Complete")
print(f"Time taken: {elapsed_time:.2f} seconds")
print(f"Blank images quarantined: {images_moved}")
print(f"Storage space saved for downstream tasks: {mb_saved:.2f} MB")