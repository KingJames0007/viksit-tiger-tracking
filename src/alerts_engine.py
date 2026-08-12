import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

# Calculate historical baseline for T-001
historical_data = {
    'latitude': [21.650, 21.661, 21.642, 21.655, 21.648],
    'longitude': [79.201, 79.215, 79.220, 79.190, 79.230]
}
df = pd.DataFrame(historical_data)
gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.longitude, df.latitude), crs="EPSG:4326")
gdf_metric = gdf.to_crs(epsg=32644)

# Cache historical centroid
CORE_CENTROID = gdf_metric.geometry.union_all().convex_hull.centroid
RANGE_SHIFT_THRESHOLD_METERS = 5000

def check_deviation(tiger_id, lat, lon):
    """
    Checks if a new GPS coordinate is too far from the historical core.
    Returns: (alert_status_string, distance_in_km)
    """
    point_gps = Point(lon, lat)
    event_gdf = gpd.GeoDataFrame([1], geometry=[point_gps], crs="EPSG:4326")
    event_metric = event_gdf.to_crs(epsg=32644)
    new_location = event_metric.geometry.iloc[0]
    
    # Calculate distance
    distance_meters = CORE_CENTROID.distance(new_location)
    distance_km = distance_meters / 1000
    
    if distance_meters >= RANGE_SHIFT_THRESHOLD_METERS:
        return "CRITICAL", distance_km
    return "NORMAL", distance_km