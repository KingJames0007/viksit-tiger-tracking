import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as transforms
from PIL import Image
import numpy as np
import faiss
import os
import json

print("Loading ResNet50 and FAISS Index into server memory...")
# 1. Initialize Deep Learning Model Globally
weights = models.ResNet50_Weights.IMAGENET1K_V2
resnet = models.resnet50(weights=weights)
model = nn.Sequential(*list(resnet.children())[:-1])
model.eval()

transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])

# 2. Initialize FAISS Database Globally with local persistence
embedding_dimension = 2048
INDEX_PATH = "data/faiss_index.bin"
DB_MAP_PATH = "data/tiger_database.json"

# Ensure data dir exists
os.makedirs("data", exist_ok=True)

if os.path.exists(INDEX_PATH) and os.path.exists(DB_MAP_PATH):
    print("Loading existing FAISS index and tiger database mapping...")
    try:
        index = faiss.read_index(INDEX_PATH)
        with open(DB_MAP_PATH, "r") as f:
            tiger_database = json.load(f)
    except Exception as e:
        print(f"Error loading index, reinitializing: {e}")
        index = faiss.IndexFlatL2(embedding_dimension)
        tiger_database = []
else:
    print("Creating new FAISS index and tiger database mapping...")
    index = faiss.IndexFlatL2(embedding_dimension)
    tiger_database = [] # Maps FAISS index rows to string IDs (e.g., "T-001")

def extract_features(image_path, bbox=None):
    """Converts an image (cropped by bbox if provided) into a normalized 2048-dimensional vector."""
    image = Image.open(image_path).convert('RGB')
    
    if bbox is not None:
        # crop format: (left, upper, right, lower)
        image = image.crop((bbox[0], bbox[1], bbox[2], bbox[3]))
        
    tensor = transform(image).unsqueeze(0)
    
    with torch.no_grad():
        features = model(tensor)
        
    vector = features.squeeze().numpy()
    # Handle single element or division by zero safely
    norm = np.linalg.norm(vector)
    if norm > 0:
        vector = vector / norm
    return vector

def match_tiger(file_path, bbox=None, auto_match_threshold=0.20, enroll_threshold=0.40):
    """
    Compares image to database. 
    Returns: (tiger_id, distance_score, status, message)
    - status: 'success' (auto matched), 'pending_review' (ambiguous), 'enrolled' (new tiger)
    """
    vector = extract_features(file_path, bbox)
    
    # If the database is completely empty, enroll the first tiger
    if index.ntotal == 0:
        new_id = "T-001"
        index.add(np.array([vector]))
        tiger_database.append(new_id)
        
        # Persist index and mapping
        faiss.write_index(index, INDEX_PATH)
        with open(DB_MAP_PATH, "w") as f:
            json.dump(tiger_database, f)
            
        return new_id, 0.0, "enrolled", "First individual enrolled"
        
    # Search the existing database
    distances, indices = index.search(np.array([vector]), 1)
    best_distance = float(distances[0][0])
    best_match_idx = int(indices[0][0])
    matched_id = tiger_database[best_match_idx]
    
    if best_distance <= auto_match_threshold:
        # Confident match
        return matched_id, best_distance, "success", f"Auto-matched with {matched_id}"
    elif best_distance <= enroll_threshold:
        # Ambiguous match - surface for human review
        return matched_id, best_distance, "pending_review", f"Ambiguous match. Close to {matched_id}"
    else:
        # Distance is too high; enroll as a new individual
        # Find next available ID based on unique count in database
        unique_tigers = set(tiger_database)
        new_id = f"T-{len(unique_tigers) + 1:03d}"
        
        index.add(np.array([vector]))
        tiger_database.append(new_id)
        
        # Persist index and mapping
        faiss.write_index(index, INDEX_PATH)
        with open(DB_MAP_PATH, "w") as f:
            json.dump(tiger_database, f)
            
        return new_id, best_distance, "enrolled", f"New individual enrolled: {new_id}"

def enroll_manually(file_path, bbox, custom_id):
    """Enrolls a tiger with a specific custom ID (used when resolving reviews or manual enrolment)."""
    vector = extract_features(file_path, bbox)
    index.add(np.array([vector]))
    tiger_database.append(custom_id)
    
    # Persist index and mapping
    faiss.write_index(index, INDEX_PATH)
    with open(DB_MAP_PATH, "w") as f:
        json.dump(tiger_database, f)