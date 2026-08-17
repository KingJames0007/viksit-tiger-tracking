from src.db import enroll_tiger, add_capture, get_db

def seed():
    print("Starting database seeding...")
    db = get_db()
    
    # 1. Clean existing records (Optional, but good for fresh seed)
    print("Clearing existing captures and alerts...")
    try:
        db.table("alerts").delete().neq("id", 0).execute()
        db.table("captures").delete().neq("id", 0).execute()
        db.table("tigers").delete().neq("id", "none").execute()
    except Exception as e:
        print("Could not clean database (might be empty):", e)

    # 2. Enroll Tigers
    print("Enrolling tigers...")
    enroll_tiger("T-001", "Machli (Core Resident)")
    enroll_tiger("T-002", "Ustad (Border Roamer)")

    # 3. Add capture history for T-001 (Core Resident)
    # Centered around Lat: 21.65, Lon: 79.20 (Core Zone)
    print("Seeding captures for T-001...")
    t1_captures = [
        {"lat": 21.650, "lon": 79.201, "station": "STATION_A01", "time": "2026-08-10T08:00:00Z"},
        {"lat": 21.661, "lon": 79.215, "station": "STATION_A02", "time": "2026-08-11T12:30:00Z"},
        {"lat": 21.642, "lon": 79.220, "station": "STATION_A03", "time": "2026-08-12T15:45:00Z"},
        {"lat": 21.655, "lon": 79.190, "station": "STATION_A04", "time": "2026-08-13T03:15:00Z"},
        {"lat": 21.648, "lon": 79.230, "station": "STATION_A05", "time": "2026-08-14T21:00:00Z"},
    ]
    for idx, cap in enumerate(t1_captures):
        add_capture(
            tiger_id="T-001",
            image_path=f"t1_historical_{idx}.jpg",
            station=cap["station"],
            timestamp=cap["time"],
            latitude=cap["lat"],
            longitude=cap["lon"],
            status="processed",
            confidence=0.95
        )

    # 4. Add capture history for T-002 (Border Roamer)
    # Centered around Lat: 21.66, Lon: 79.23 (Slightly East, overlaps with T-001)
    print("Seeding captures for T-002...")
    t2_captures = [
        {"lat": 21.660, "lon": 79.218, "station": "STATION_A02", "time": "2026-08-11T09:15:00Z"}, # STATION_A02 is an overlap station!
        {"lat": 21.675, "lon": 79.240, "station": "STATION_A06", "time": "2026-08-12T18:20:00Z"},
        {"lat": 21.668, "lon": 79.225, "station": "STATION_A07", "time": "2026-08-13T11:40:00Z"},
        {"lat": 21.658, "lon": 79.250, "station": "STATION_A08", "time": "2026-08-14T04:50:00Z"},
    ]
    for idx, cap in enumerate(t2_captures):
        add_capture(
            tiger_id="T-002",
            image_path=f"t2_historical_{idx}.jpg",
            station=cap["station"],
            timestamp=cap["time"],
            latitude=cap["lat"],
            longitude=cap["lon"],
            status="processed",
            confidence=0.93
        )

    print("Seeding complete! Run the FastAPI server and trigger alerts checking next.")

if __name__ == "__main__":
    seed()
