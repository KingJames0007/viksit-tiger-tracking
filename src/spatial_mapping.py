import pandas as pd
import geopandas as gpd
from shapely.geometry import MultiPoint, Polygon
from src.db import get_db

def calculate_territory(tiger_id):
    """
    Fetches captures from Supabase and calculates the MCP (Minimum Convex Polygon).
    Returns: (area_in_sqkm, centroid_dict, polygon_coordinates)
    - area_in_sqkm: float
    - centroid_dict: {"lat": float, "lon": float}
    - polygon_coordinates: list of [lat, lon] pairs for Leaflet mapping
    """
    db = get_db()
    
    # Query captures for this tiger from Supabase
    try:
        res = db.table("captures")\
                .select("latitude, longitude, station, timestamp")\
                .eq("tiger_id", tiger_id)\
                .eq("status", "processed")\
                .execute()
        points = res.data
    except Exception as e:
        print(f"Error querying captures for tiger {tiger_id}: {e}")
        points = []
            
    if not points:
        return 0.0, None, []
        
    capture_points = [{"lat": p["latitude"], "lon": p["longitude"], "station": p["station"], "timestamp": p["timestamp"]} for p in points]
    
    # Need at least 3 points to draw a polygon
    if len(points) < 3:
        avg_lat = sum(p["latitude"] for p in points) / len(points)
        avg_lon = sum(p["longitude"] for p in points) / len(points)
        return 0.0, {"lat": avg_lat, "lon": avg_lon}, []
        
    # Extract coordinates
    lats = [p["latitude"] for p in points]
    lons = [p["longitude"] for p in points]
    
    df = pd.DataFrame({"latitude": lats, "longitude": lons})
    gdf = gpd.GeoDataFrame(
        df, 
        geometry=gpd.points_from_xy(df.longitude, df.latitude),
        crs="EPSG:4326"
    )
    
    # Project to metric system (UTM Zone 44N covers Central India)
    gdf_metric = gdf.to_crs(epsg=32644)
    multipoint = MultiPoint(gdf_metric.geometry.tolist())
    
    # Convex Hull
    mcp = multipoint.convex_hull
    
    # If the convex hull is a Point or LineString (collinear points)
    if not isinstance(mcp, Polygon):
        centroid_metric = mcp.centroid
        centroid_gps = gpd.GeoSeries([centroid_metric], crs="EPSG:32644").to_crs(epsg=4326).iloc[0]
        return 0.0, {"lat": centroid_gps.y, "lon": centroid_gps.x}, []
        
    # Calculate area in sq km
    area_sqkm = mcp.area / 1_000_000
    
    # Get centroid and project back to GPS (EPSG:4326)
    centroid_metric = mcp.centroid
    centroid_gps = gpd.GeoSeries([centroid_metric], crs="EPSG:32644").to_crs(epsg=4326).iloc[0]
    
    # Project boundary back to GPS
    exterior_coords = list(mcp.exterior.coords)
    boundary_gdf = gpd.GeoDataFrame(
        geometry=[Polygon(exterior_coords)],
        crs="EPSG:32644"
    ).to_crs(epsg=4326)
    
    boundary_polygon = list(boundary_gdf.geometry.iloc[0].exterior.coords)
    # Convert boundary coords from [lon, lat] to [lat, lon] for Leaflet
    polygon_gps = [[coord[1], coord[0]] for coord in boundary_polygon]
    
    return area_sqkm, {"lat": centroid_gps.y, "lon": centroid_gps.x}, polygon_gps

def get_territory_overlaps():
    """
    Calculates territorial overlaps between all tigers with calculated polygons.
    Returns list of overlap info, including intersection polygon coordinates and area.
    """
    db = get_db()
    try:
        res_tigers = db.table("tigers").select("id").execute()
        tiger_ids = [t["id"] for t in res_tigers.data]
    except Exception as e:
        print(f"Error fetching tigers for overlap: {e}")
        return []
    
    geometries = {}
    
    for t_id in tiger_ids:
        try:
            res = db.table("captures")\
                    .select("latitude, longitude")\
                    .eq("tiger_id", t_id)\
                    .eq("status", "processed")\
                    .execute()
            points = res.data
        except Exception as e:
            print(f"Error fetching captures: {e}")
            points = []
            
        if len(points) >= 3:
            lats = [p["latitude"] for p in points]
            lons = [p["longitude"] for p in points]
            df = pd.DataFrame({"latitude": lats, "longitude": lons})
            gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.longitude, df.latitude), crs="EPSG:4326")
            gdf_metric = gdf.to_crs(epsg=32644)
            mcp = MultiPoint(gdf_metric.geometry.tolist()).convex_hull
            if isinstance(mcp, Polygon):
                geometries[t_id] = mcp
                
    overlaps = []
    keys = list(geometries.keys())
    for i in range(len(keys)):
        for j in range(i+1, len(keys)):
            t1 = keys[i]
            t2 = keys[j]
            geom1 = geometries[t1]
            geom2 = geometries[t2]
            
            if geom1.intersects(geom2):
                intersection = geom1.intersection(geom2)
                if isinstance(intersection, Polygon):
                    overlap_area = intersection.area / 1_000_000
                    # Project intersection back to GPS to draw
                    boundary_gdf = gpd.GeoDataFrame(geometry=[intersection], crs="EPSG:32644").to_crs(epsg=4326)
                    coords = list(boundary_gdf.geometry.iloc[0].exterior.coords)
                    polygon_gps = [[c[1], c[0]] for c in coords]
                    
                    overlaps.append({
                        "tiger_1": t1,
                        "tiger_2": t2,
                        "overlap_area_sqkm": round(overlap_area, 4),
                        "polygon": polygon_gps
                    })
                    
    return overlaps