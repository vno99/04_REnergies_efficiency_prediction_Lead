import requests as rq
import pandas as pd
import os 
import geopandas as gpd
import json
from geojson import Polygon, Feature, FeatureCollection, dump

# Helper function from your notebooks
def fetch_stac_server(params):
    '''
    Queries the STAC server (STAC) backend.
    params is a Python dictionary to pass as JSON to the request.
    '''
    
    search_url = f"https://landsatlook.usgs.gov/stac-server/search"
    query_return = rq.post(search_url, json=params).json()
    error = query_return.get("message", "")
    if error:
        raise Exception(f"STAC-Server failed and returned: {error}")
        
    if 'code' in query_return:
        print(query_return)   
    else:
        print(f"{len(query_return['features'])} STAC items found")
        return query_return['features']

def create_param_payload(limit=None, daterange=None, bbox=None, intersects=None, collections=None, query=None, sortby=None, fields=None):
    """
    Create a parameter payload dictionary for a query.

    Parameters:
    - limit (int, optional): Return limit. Default 20
    - daterange (str, optional): Date range in the format 'start_date/end_date' in ISO 8601 format.
    - bbox (list of float, optional): Bounding box in the format [min_lon, min_lat, max_lon, max_lat].
    - interects (GeoJSON object, optional): Intersects filters the result items to return scenes that intersect the input GeoJSON object
    - collections (str or list of str, optional): Collection ID(s).
    - query (dict, optional): Dictionary of query parameters.
    - sortby (dict, optional): Choose property to sort returned results by
    - fields (dict, optional): Choose what fields to "include" or "exclude" in returned results

    Returns:
    dict: Parameter dictionary for the query.
    """
    params = {}

    if limit is not None:
        params['limit'] = limit
    else:
        params['limit'] = 10
        
    if bbox is not None:
        params['bbox'] = bbox
    
    if bbox and len(bbox) != 4:
        raise ValueError("bbox must have exactly 4 coordinates")
    
    if intersects is not None:
        params['intersects'] = intersects

    if daterange is not None:
        params['datetime'] = daterange

    if collections is not None:
        params['collections'] = collections if isinstance(collections, list) else [collections]

    if query is not None:
        params['query'] = query
        
    if sortby is not None:
        params['sortby'] = sortby
    
    if fields is not None:
        params['fields'] = fields
    
    return params


# Setting area of interest (AOI)

aoi_gdf = gpd.read_file(os.path.join("utils", 'region-auvergne-rhone-alpes.geojson')) #aoi geopandas dataframe
# using centroid instead of one of the bound values. 
# Assuming aoi_gdf is GeoDataFrame
centroid = aoi_gdf.geometry.centroid
# centroid as a coordinate pair
point = [centroid.x.values[0], centroid.y.values[0]]

#setting up params
params = create_param_payload(
    limit=2500, # Adjust as needed
    collections =["landsat-c2l2-st"],  # Level-2 SR and ST have cloud cover
    intersects = {'type': 'Point', 'coordinates': point},
    daterange = '2013-01-01T00:00:00Z/2025-11-10T23:59:59Z'
    )

# results from STAC
results = fetch_stac_server(params)

# Choose the metadata fields you want as columns, create a list of dicts
rows = []
for item in results:
    row = {
        "landsat_product_id": item.get("id"),
        "description": item.get("description"),
        "acquisition_date_time": item["properties"].get("datetime"),
        "platform": item["properties"].get("platform"),
        "scene_cloud_cover_l1": item["properties"].get("eo:cloud_cover"),
        "land_cloud_cover_l1": item["properties"].get("landsat:cloud_cover_land"),
        "sun_azimuth": item["properties"].get("view:sun_azimuth"),
        "sun_elevation": item["properties"].get("view:sun_elevation"),
        "number_of_assets": len(item.get("assets", {})),
        # Add more column mappings here as needed. Look at JSON file
        # "Other Property": item["properties"].get("other_field"),
    }
    rows.append(row)

# Create DataFrame
df = pd.DataFrame(rows)

# Current script directory
current_dir = os.path.dirname(__file__)

# Go up two folders, then into ""
target_dir = os.path.join(current_dir, "..", "..", "data/LandSat/STAC")
# Normalize the path (resolves .. and .)
target_dir = os.path.abspath(target_dir)

# Save file to CSV
file_path = os.path.join(target_dir, "landsat_metadata_query_results.csv")
df.to_csv(file_path, index=False)
print("CSV saved as landsat_query_results.csv")

# (Optional) Display the DataFrame
print("data sample")
print(df.head(5))

# Save full results to json file (execute py.script from Root directory REnergies_efficiency_prediction/
file_path = os.path.join(target_dir, "landsat_stac_metadata_raw_results.json")
with open(file_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print("Full results structure saved to data/LandSat/STAC/landsat_stac_raw_results.json")
