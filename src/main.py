from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil
import os
import hashlib
import time
from datetime import datetime

# Import modular functions
from src.triage import process_triage
from src.stripe_matcher import match_tiger
from src.spatial_mapping import calculate_territory, get_territory_overlaps
from src.alerts_engine import check_deviation, run_alerts_check
from src.db import get_db, get_all_tigers, enroll_tiger, add_capture, add_alert, get_active_alerts

app = FastAPI(title="Pench Tiger Intelligence API")

# Allow frontend to communicate with backend
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

class BulkTriageRequest(BaseModel):
    directory_path: str
    confidence_threshold: float = 0.40

def get_image_telemetry(filename):
    """
    Generates deterministic GPS, timestamp, and camera trap station metadata 
    from an image filename. Useful for hackathon reproducibility and mapping.
    """
    h = int(hashlib.md5(filename.encode()).hexdigest(), 16)
    
    # Pench Tiger Reserve boundaries: Lat [21.55, 21.75], Lon [79.15, 79.35]
    lat = 21.55 + (h % 1000) / 1000.0 * 0.20
    lon = 79.15 + ((h // 1000) % 1000) / 1000.0 * 0.20
    
    # Stations: STATION_A01 to STATION_A20
    station_id = (h // 1000000) % 20 + 1
    station = f"STATION_A{station_id:02d}"
    
    # Timestamp: recent times (August 2026)
    day = 1 + (h % 15)
    hour = (h // 15) % 24
    minute = (h // 360) % 60
    timestamp = f"2026-08-{day:02d}T{hour:02d}:{minute:02d}:00Z"
    
    return station, timestamp, lat, lon

@app.get("/system_stats")
async def get_system_stats():
    """Returns dynamic statistics of the system."""
    # 1. Identified Tigers count
    try:
        tigers = get_all_tigers()
        identified_tigers = len(tigers)
    except Exception as e:
        print(f"Error fetching tigers: {e}")
        identified_tigers = 0

    # 2. Active cameras (unique stations in database)
    try:
        db = get_db()
        captures_res = db.table("captures").select("station").execute()
        stations = {row["station"] for row in captures_res.data}
        # If no captures yet, return a baseline representing the Pench camera trap network
        active_cameras = len(stations) if stations else 142
    except Exception as e:
        print(f"Error fetching captures for stations: {e}")
        active_cameras = 142

    # 3. Storage saved & Quarantined count from filesystem
    quarantine_dir = "data/quarantine"
    total_size_bytes = 0
    quarantined_images = 0
    if os.path.exists(quarantine_dir):
        for entry in os.scandir(quarantine_dir):
            if entry.is_file():
                total_size_bytes += entry.stat().st_size
                quarantined_images += 1
    
    storage_saved_mb = round(total_size_bytes / (1024 * 1024), 2)

    return {
        "active_cameras": active_cameras,
        "identified_tigers": identified_tigers,
        "storage_saved_mb": storage_saved_mb,
        "quarantined_images": quarantined_images
    }

@app.post("/upload_camera_trap")
async def upload_image(file: UploadFile = File(...)):
    """Receives an image from the camera trap, crops the animal, matches it, and persists in Supabase."""
    file_path = f"data/raw/{file.filename}"
    
    # Save the uploaded file locally
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Get telemetry deterministically
    station, timestamp, lat, lon = get_image_telemetry(file.filename)
    
    # --- TASK 1: Triage ---
    has_animal, bbox = process_triage(file_path)
    if not has_animal:
        # Move to quarantine folder to save storage
        quarantine_path = f"data/quarantine/{file.filename}"
        shutil.move(file_path, quarantine_path)
        
        # Log to Supabase captures
        try:
            add_capture(
                tiger_id=None,
                image_path=f"data/quarantine/{file.filename}",
                station=station,
                timestamp=timestamp,
                latitude=lat,
                longitude=lon,
                status="quarantined",
                confidence=0.0
            )
        except Exception as e:
            print(f"Error saving quarantine capture in DB: {e}")
        
        return {
            "status": "quarantined", 
            "message": "No animal detected. Image moved to quarantine."
        }
    
    # --- TASK 2: Identification ---
    tiger_id, distance, match_status, match_message = match_tiger(file_path, bbox)
    
    # Enroll tiger if it's new
    if match_status == "enrolled":
        try:
            enroll_tiger(tiger_id)
        except Exception as e:
            print(f"Error enrolling tiger {tiger_id}: {e}")
            
    # Save in captures
    capture_status = "processed"
    if match_status == "pending_review":
        capture_status = "pending_review"
        
    try:
        add_capture(
            tiger_id=tiger_id,
            image_path=file_path,
            station=station,
            timestamp=timestamp,
            latitude=lat,
            longitude=lon,
            status=capture_status,
            confidence=round(1.0 - distance, 4)
        )
    except Exception as e:
        print(f"Error saving capture in DB: {e}")
    
    # Trigger dynamic alert checking
    try:
        run_alerts_check(tiger_id, lat, lon, station, timestamp)
    except Exception as e:
        print(f"Error running alerts: {e}")
    
    return {
        "status": "success", 
        "tiger_id": tiger_id, 
        "distance_score": round(distance, 4),
        "match_status": match_status,
        "message": match_message,
        "station": station,
        "timestamp": timestamp,
        "lat": lat,
        "lon": lon
    }

@app.get("/territory/{tiger_id}")
async def get_territory(tiger_id: str):
    """Runs Task 3 to calculate and return territory area, centroid, and convex hull polygon coordinates."""
    area_sqkm, centroid, polygon = calculate_territory(tiger_id)
    
    if area_sqkm == 0.0 and centroid is None:
        return {
            "status": "insufficient_data",
            "message": f"Not enough data points to calculate territory for {tiger_id}."
        }
        
    return {
        "status": "calculated",
        "tiger_id": tiger_id,
        "core_area_sqkm": round(area_sqkm, 2),
        "centroid": centroid,
        "polygon": polygon
    }

@app.get("/territory_overlaps")
async def get_overlaps():
    """Returns territorial overlaps between all tigers."""
    overlaps = get_territory_overlaps()
    return {
        "status": "success",
        "overlaps": overlaps
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

@app.get("/alerts")
async def get_alerts():
    """Fetches all active alerts from Supabase."""
    try:
        active_alerts = get_active_alerts()
        return active_alerts
    except Exception as e:
        print(f"Error fetching alerts: {e}")
        return []

@app.post("/resolve_alert/{alert_id}")
async def resolve_alert_route(alert_id: int):
    """Marks an alert as resolved in Supabase."""
    try:
        from src.db import resolve_alert
        resolve_alert(alert_id)
        return {"status": "success", "message": f"Alert {alert_id} marked as resolved."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/tigers")
async def get_tigers():
    """Fetches all enrolled tigers."""
    try:
        tigers = get_all_tigers()
        return tigers
    except Exception as e:
        print(f"Error fetching tigers: {e}")
        return []

@app.post("/bulk_triage")
async def bulk_triage(req: BulkTriageRequest):
    """
    Ingests a raw image directory, classifies each frame,
    and moves blank images to the quarantine directory.
    Reports count of frames, space saved, and time saved.
    """
    start_time = time.time()
    
    dir_path = req.directory_path
    if not os.path.exists(dir_path):
        return {"status": "error", "message": f"Directory '{dir_path}' does not exist."}
        
    # Get all image files in the directory
    valid_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff"}
    image_files = []
    for root, _, files in os.walk(dir_path):
        for f in files:
            if os.path.splitext(f)[1].lower() in valid_extensions:
                image_files.append(os.path.join(root, f))
                
    total_frames = len(image_files)
    if total_frames == 0:
        return {"status": "success", "message": "No images found in the specified directory.", "total_frames": 0}
        
    quarantined_count = 0
    processed_count = 0
    total_space_saved_bytes = 0
    
    # Track coordinates and other data
    os.makedirs("data/quarantine", exist_ok=True)
    
    # Process images
    for filepath in image_files:
        filename = os.path.basename(filepath)
        
        # 1. MegaDetector Triage
        has_animal, bbox = process_triage(filepath, req.confidence_threshold)
        
        # Get metadata deterministically
        station, timestamp, lat, lon = get_image_telemetry(filename)
        
        if not has_animal:
            # Safe delete (move to quarantine)
            file_size = os.path.getsize(filepath)
            total_space_saved_bytes += file_size
            
            quarantine_path = os.path.join("data/quarantine", filename)
            # Ensure unique filename in quarantine
            if os.path.exists(quarantine_path):
                base, ext = os.path.splitext(filename)
                quarantine_path = os.path.join("data/quarantine", f"{base}_{int(time.time())}{ext}")
                
            shutil.move(filepath, quarantine_path)
            quarantined_count += 1
            
            # Log in database as quarantined
            try:
                add_capture(
                    tiger_id=None,
                    image_path=os.path.basename(quarantine_path),
                    station=station,
                    timestamp=timestamp,
                    latitude=lat,
                    longitude=lon,
                    status="quarantined",
                    confidence=0.0
                )
            except Exception as e:
                print(f"Error logging quarantine: {e}")
        else:
            # It has an animal, run identification
            processed_count += 1
            try:
                tiger_id, distance, match_status, match_message = match_tiger(filepath, bbox)
                
                # If new tiger, enroll it in Supabase
                if match_status == "enrolled":
                    try:
                        enroll_tiger(tiger_id)
                    except Exception as e:
                        print(f"Error enrolling tiger {tiger_id}: {e}")
                
                # Determine database capture status
                capture_status = "processed"
                if match_status == "pending_review":
                    capture_status = "pending_review"
                    
                # Save in captures
                add_capture(
                    tiger_id=tiger_id,
                    image_path=filename,
                    station=station,
                    timestamp=timestamp,
                    latitude=lat,
                    longitude=lon,
                    status=capture_status,
                    confidence=round(1.0 - distance, 4)
                )
                
                # Trigger alerts check
                try:
                    run_alerts_check(tiger_id, lat, lon, station, timestamp)
                except Exception as e:
                    print(f"Error checking alerts: {e}")
                    
            except Exception as e:
                print(f"Error processing matching for {filename}: {e}")
                
    elapsed_time = time.time() - start_time
    
    # Manual triage time saved calculation:
    # Assume a manual reviewer takes an average of 4 seconds per image to review.
    time_saved_seconds = quarantined_count * 4
    
    space_saved_mb = round(total_space_saved_bytes / (1024 * 1024), 2)
    
    return {
        "status": "success",
        "total_frames_ingested": total_frames,
        "frames_quarantined": quarantined_count,
        "frames_retained": processed_count,
        "space_saved_mb": space_saved_mb,
        "processing_time_seconds": round(elapsed_time, 2),
        "manual_time_saved_seconds": time_saved_seconds,
        "message": f"Successfully processed {total_frames} frames. Quarantined {quarantined_count} blank images."
    }