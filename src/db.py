import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Load environment variables from .env
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
# Prefer service role key for admin database operations (bypassing RLS in hackathon)
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set in the .env file")

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_db():
    return supabase

# --- Tigers Table Helper Functions ---

def enroll_tiger(tiger_id: str, name: str = None):
    """Enrolls a new tiger in the tigers database."""
    data = {"id": tiger_id, "name": name or f"Tiger {tiger_id}"}
    response = supabase.table("tigers").upsert(data).execute()
    return response.data

def get_tiger(tiger_id: str):
    """Retrieves a tiger record by ID."""
    response = supabase.table("tigers").select("*").eq("id", tiger_id).execute()
    return response.data[0] if response.data else None

def get_all_tigers():
    """Retrieves all tigers enrolled in the database."""
    response = supabase.table("tigers").select("*").execute()
    return response.data

# --- Captures Table Helper Functions ---

def add_capture(tiger_id: str, image_path: str, station: str, timestamp: str, latitude: float, longitude: float, status: str, confidence: float):
    """Logs a new camera trap capture."""
    data = {
        "tiger_id": tiger_id,
        "image_path": image_path,
        "station": station,
        "timestamp": timestamp,
        "latitude": latitude,
        "longitude": longitude,
        "status": status,
        "confidence": confidence
    }
    response = supabase.table("captures").insert(data).execute()
    return response.data

def get_captures_for_tiger(tiger_id: str):
    """Fetches all captures for a specific tiger."""
    response = supabase.table("captures").select("*").eq("tiger_id", tiger_id).execute()
    return response.data

def get_all_captures():
    """Fetches all captures."""
    response = supabase.table("captures").select("*").execute()
    return response.data

# --- Alerts Table Helper Functions ---

def add_alert(tiger_id: str, alert_type: str, severity: str, message: str, evidence: dict = None):
    """Inserts a new deviation/trend alert."""
    data = {
        "tiger_id": tiger_id,
        "alert_type": alert_type,
        "severity": severity,
        "message": message,
        "evidence": evidence or {}
    }
    response = supabase.table("alerts").insert(data).execute()
    return response.data

def get_active_alerts():
    """Retrieves all unresolved alerts, sorted by newest first."""
    response = supabase.table("alerts").select("*").eq("resolved", False).order("timestamp", desc=True).execute()
    return response.data

def resolve_alert(alert_id: int):
    """Marks an alert as resolved."""
    response = supabase.table("alerts").update({"resolved": True}).eq("id", alert_id).execute()
    return response.data
