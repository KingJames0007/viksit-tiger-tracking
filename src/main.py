from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import os

# Import the modular functions from your AI scripts
from src.triage import process_triage
from src.stripe_matcher import match_tiger
from src.spatial_mapping import calculate_territory
from src.alerts_engine import check_deviation

app = FastAPI(title="Pench Tiger Intelligence API")

# CRITICAL FOR HACKATHONS: Allow frontend to communicate with backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure data directories exist
os.makedirs("data/raw", exist_ok=True)
os.makedirs("data/quarantine", exist_ok=True)

# Define the data structure for incoming GPS pings
class GPSPing(BaseModel):
    tiger_id: str
    lat: float
    lon: float
    timestamp: str

@app.post("/upload_camera_trap")
async def upload_image(file: UploadFile = File(...)):
    """Receives an image from the camera trap and runs Task 1 & 2."""
    file_path = f"data/raw/{file.filename}"
    
    # Save the uploaded file locally
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # --- TASK 1: Triage ---
    has_animal = process_triage(file_path)
    if not has_animal:
        # Move to quarantine folder to save storage
        quarantine_path = f"data/quarantine/{file.filename}"
        shutil.move(file_path, quarantine_path)
        return {
            "status": "quarantined", 
            "message": "No animal detected. Image moved to quarantine."
        }
    
    # --- TASK 2: Identification ---
    tiger_id, distance, match_message = match_tiger(file_path)
    
    return {
        "status": "success", 
        "tiger_id": tiger_id, 
        "distance_score": round(distance, 4),
        "message": match_message
    }

@app.get("/territory/{tiger_id}")
async def get_territory(tiger_id: str):
    """Runs Task 3 to calculate and return territory area and centroid."""
    area_sqkm, centroid = calculate_territory(tiger_id)
    
    if area_sqkm == 0.0:
        return {
            "status": "insufficient_data",
            "message": f"Not enough data points to calculate territory for {tiger_id} (requires at least 3)."
        }
        
    return {
        "status": "calculated",
        "tiger_id": tiger_id,
        "core_area_sqkm": round(area_sqkm, 2),
        "centroid": centroid
    }

@app.post("/check_alerts")
async def check_alerts(ping: GPSPing):
    """Runs Task 4 to check if a new GPS coordinate triggers a deviation alert."""
    alert_status, distance_km = check_deviation(ping.tiger_id, ping.lat, ping.lon)
    
    if alert_status == "CRITICAL":
        message = f"🚨 RANGE SHIFT DETECTED! Tiger {ping.tiger_id} has deviated {distance_km:.2f}km from core range."
    else:
        message = f"Normal movement. Tiger {ping.tiger_id} is {distance_km:.2f}km from core center."
        
    return {
        "alert": alert_status,
        "distance_km": round(distance_km, 2),
        "message": message
    }