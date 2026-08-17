from shapely.geometry import Point
import geopandas as gpd
import pandas as pd
import json
from datetime import datetime
from src.db import get_db, add_alert

def is_buffer_station(lat, lon):
    """Core Box: Lat [21.61, 21.71], Lon [79.19, 79.29]. Anything outside is buffer."""
    in_core = (21.61 <= lat <= 21.71) and (79.19 <= lon <= 79.29)
    return not in_core

def is_village_adjacent(lat, lon):
    """Village boundaries near buffer edges: South boundary (< 21.57) or East boundary (> 79.33)."""
    return (lat < 21.57) or (lon > 79.33)

def run_alerts_check(tiger_id, lat, lon, station, timestamp):
    """
    Compares the current capture event to historical baseline and triggers alerts
    for range shifts, first station capture, buffer proximity, or village adjacency.
    """
    db = get_db()
    
    # Fetch captures for this tiger, ordered by timestamp descending
    try:
        res = db.table("captures")\
                .select("id, latitude, longitude, station, timestamp")\
                .eq("tiger_id", tiger_id)\
                .eq("status", "processed")\
                .order("timestamp", desc=True)\
                .execute()
        captures = res.data
    except Exception as e:
        print(f"Error querying captures in alerts check: {e}")
        return
        
    if len(captures) <= 1:
        # First capture of this tiger, no baseline to compare against
        return
        
    # Current capture is captures[0]
    # History is captures[1:]
    history = captures[1:]
    
    # 1. Check for range shift (Distance from historical centroid)
    hist_lats = [c["latitude"] for c in history]
    hist_lons = [c["longitude"] for c in history]
    
    df_hist = pd.DataFrame({"latitude": hist_lats, "longitude": hist_lons})
    gdf_hist = gpd.GeoDataFrame(df_hist, geometry=gpd.points_from_xy(df_hist.longitude, df_hist.latitude), crs="EPSG:4326")
    gdf_hist_metric = gdf_hist.to_crs(epsg=32644)
    
    # Calculate union centroid
    centroid_metric = gdf_hist_metric.geometry.union_all().centroid
    
    # Current location
    current_pt = gpd.GeoDataFrame([1], geometry=[Point(lon, lat)], crs="EPSG:4326").to_crs(epsg=32644).geometry.iloc[0]
    
    # Distance in meters
    distance_meters = centroid_metric.distance(current_pt)
    distance_km = distance_meters / 1000.0
    
    is_current_in_buffer = is_buffer_station(lat, lon)
    
    # Thresholds: 5km in buffer, 4km in core (corresponding to ~15-20 sq km area displacement)
    threshold_km = 5.0 if is_current_in_buffer else 4.0
    
    if distance_km >= threshold_km:
        region = "BUFFER" if is_current_in_buffer else "CORE"
        msg = f"🚨 RANGE SHIFT DETECTED! Tiger {tiger_id} has deviated {distance_km:.2f} km from its historical core center in the {region} zone."
        evidence = {
            "distance_km": distance_km,
            "threshold_km": threshold_km,
            "region": region,
            "current_location": {"lat": lat, "lon": lon}
        }
        try:
            add_alert(tiger_id, "RANGE_SHIFT", "CRITICAL", msg, evidence)
        except Exception as e:
            print(f"Error adding range shift alert: {e}")

    # 2. Check for first capture at previously unused station
    historical_stations = {c["station"] for c in history}
    if station not in historical_stations and station != "GPS_PING":
        msg = f"📍 NEW STATION DETECTED! Tiger {tiger_id} captured at station {station} for the first time."
        evidence = {
            "station": station,
            "historical_stations": list(historical_stations)
        }
        try:
            add_alert(tiger_id, "NEW_STATION", "INFO", msg, evidence)
        except Exception as e:
            print(f"Error adding new station alert: {e}")

    # 3. Check for movement into/towards Buffer or Village-adjacent stations
    prev_capture = history[0]
    prev_lat, prev_lon = prev_capture["latitude"], prev_capture["longitude"]
    was_prev_in_core = not is_buffer_station(prev_lat, prev_lon)
    
    if is_current_in_buffer and was_prev_in_core:
        msg = f"⚠️ CORE TO BUFFER MOVEMENT! Tiger {tiger_id} has moved from core forest into the buffer zone (Station: {station})."
        evidence = {
            "from_station": prev_capture["station"],
            "to_station": station,
            "current_location": {"lat": lat, "lon": lon}
        }
        try:
            add_alert(tiger_id, "BUFFER_PROXIMITY", "WARNING", msg, evidence)
        except Exception as e:
            print(f"Error adding core to buffer alert: {e}")
        
    if is_village_adjacent(lat, lon):
        msg = f"🚨 VILLAGE ADJACENT CAPTURE! Tiger {tiger_id} detected at {station} close to human settlement borders."
        evidence = {
            "station": station,
            "current_location": {"lat": lat, "lon": lon}
        }
        try:
            add_alert(tiger_id, "BUFFER_PROXIMITY", "CRITICAL", msg, evidence)
        except Exception as e:
            print(f"Error adding village adjacent alert: {e}")

def check_deviation(tiger_id, lat, lon):
    """
    Checks range deviation for a single coordinate ping.
    This maintains compatibility with existing REST endpoints.
    """
    db = get_db()
    
    # 1. Fetch captures to calculate baseline
    try:
        res = db.table("captures")\
                .select("latitude, longitude")\
                .eq("tiger_id", tiger_id)\
                .eq("status", "processed")\
                .execute()
        points = res.data
    except Exception as e:
        print(f"Error fetching captures for check_deviation: {e}")
        points = []
        
    if not points:
        return "NORMAL", 0.0
        
    df_hist = pd.DataFrame(points)
    gdf_hist = gpd.GeoDataFrame(df_hist, geometry=gpd.points_from_xy(df_hist.longitude, df_hist.latitude), crs="EPSG:4326")
    gdf_hist_metric = gdf_hist.to_crs(epsg=32644)
    centroid_metric = gdf_hist_metric.geometry.union_all().centroid
    
    current_pt = gpd.GeoDataFrame([1], geometry=[Point(lon, lat)], crs="EPSG:4326").to_crs(epsg=32644).geometry.iloc[0]
    distance_meters = centroid_metric.distance(current_pt)
    distance_km = distance_meters / 1000.0
    
    # 2. Call run_alerts_check to log alerts if any
    run_alerts_check(tiger_id, lat, lon, "GPS_PING", datetime.utcnow().isoformat() + "Z")
    
    is_buffer = is_buffer_station(lat, lon)
    threshold_km = 5.0 if is_buffer else 4.0
    
    if distance_km >= threshold_km or is_village_adjacent(lat, lon):
        return "CRITICAL", distance_km
        
    return "NORMAL", distance_km