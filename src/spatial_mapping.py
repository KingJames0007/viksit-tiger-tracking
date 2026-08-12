import pandas as pd
import geopandas as gpd
from shapely.geometry import MultiPoint

# Mock Database of GPS coordinates
MOCK_DB = {
    'tiger_id': ['T-001', 'T-001', 'T-001', 'T-001', 'T-001', 'T-002', 'T-002', 'T-002'],
    'latitude': [21.650, 21.661, 21.642, 21.655, 21.648, 21.660, 21.675, 21.668],
    'longitude': [79.201, 79.215, 79.220, 79.190, 79.230, 79.218, 79.240, 79.225]
}

def calculate_territory(tiger_id):
    """
    Calculates the territory area and core centroid for a given tiger.
    Returns: (area_in_sqkm, centroid_dict)
    """
    df = pd.DataFrame(MOCK_DB)
    tiger_df = df[df['tiger_id'] == tiger_id]
    
    # Need at least 3 points to draw a polygon
    if len(tiger_df) < 3:
        return 0.0, None
        
    gdf = gpd.GeoDataFrame(
        tiger_df, 
        geometry=gpd.points_from_xy(tiger_df.longitude, tiger_df.latitude),
        crs="EPSG:4326"
    )
    
    # Project to metric to calculate square kilometers
    gdf_metric = gdf.to_crs(epsg=32644)
    multipoint = MultiPoint(gdf_metric.geometry.tolist())
    mcp = multipoint.convex_hull
    area_sqkm = mcp.area / 1_000_000
    
    # Convert centroid back to GPS coordinates for plotting
    centroid_metric = gpd.GeoSeries([mcp.centroid], crs="EPSG:32644")
    centroid_gps = centroid_metric.to_crs(epsg=4326).iloc[0]
    
    return area_sqkm, {"lat": centroid_gps.y, "lon": centroid_gps.x}