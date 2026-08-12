import torch
import torch.nn as nn
import torchvision.models as models
import torchvision.transforms as transforms
from PIL import Image
import numpy as np
import faiss

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

# 2. Initialize FAISS Database Globally
embedding_dimension = 2048
index = faiss.IndexFlatL2(embedding_dimension)
tiger_database = [] # Maps FAISS index rows to string IDs (e.g., "T-001")

def extract_features(image_path):
    """Converts an image into a normalized 2048-dimensional vector."""
    image = Image.open(image_path).convert('RGB')
    tensor = transform(image).unsqueeze(0)
    
    with torch.no_grad():
        features = model(tensor)
        
    vector = features.squeeze().numpy()
    return vector / np.linalg.norm(vector)

def match_tiger(file_path, distance_threshold=0.35):
    """
    Compares image to database. 
    Returns: (tiger_id, distance_score, status_message)
    """
    vector = extract_features(file_path)
    
    # If the database is completely empty, enroll the first tiger
    if index.ntotal == 0:
        new_id = "T-001"
        index.add(np.array([vector]))
        tiger_database.append(new_id)
        return new_id, 0.0, "New individual enrolled"
        
    # Search the existing database
    distances, indices = index.search(np.array([vector]), 1)
    best_distance = distances[0][0]
    best_match_idx = indices[0][0]
    
    # If distance is low enough, it's a known tiger
    if best_distance <= distance_threshold:
        matched_id = tiger_database[best_match_idx]
        return matched_id, float(best_distance), "Existing tiger identified"
    else:
        # Distance is too high; enroll as a new individual
        new_id = f"T-{index.ntotal + 1:03d}"
        index.add(np.array([vector]))
        tiger_database.append(new_id)
        return new_id, float(best_distance), "New individual enrolled"