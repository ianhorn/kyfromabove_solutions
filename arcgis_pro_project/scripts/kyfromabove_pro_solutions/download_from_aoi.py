"""

Author: Ian Horn
Date: June 8, 2026

    1. Select an area of interest
    2. Run stac api against geometry (point, line, polygon)
    3. Download imagery

"""

import os
from pathlib import Path
from urllib.parse import urlparse
import requests
import arcpy
import pandas as pd
from concurrent.futures import ThreadPoolExecutor\


MAX_WORKERS = max(1, int(os.cpu_count() * 0.75))


# -------------------------------------------------------------------
# Environment
# -------------------------------------------------------------------

arcpy.env.workspace = os.getcwd()
arcpy.env.parallelProcessingFactor = "75%"


# -------------------------------------------------------------------
# Parameters
# -------------------------------------------------------------------

AOI = arcpy.GetParameterAsText(0)
DOWNLOAD_FOLDER = Path(arcpy.GetParameterAsText(1))
TILE_GRID = arcpy.GetParameterAsText(2)
URL_FIELD = arcpy.GetParameterAsText(3) or "Phase3_url"


# -------------------------------------------------------------------
# Ensure download folder exists
# -------------------------------------------------------------------

DOWNLOAD_FOLDER.mkdir(parents=True, exist_ok=True)

arcpy.AddMessage(f"Ensured folder exists: {DOWNLOAD_FOLDER}")


# -------------------------------------------------------------------
# Make feature layer

# We need to make sure the TILE_GRID layer is something pro 
# can work with.
# -------------------------------------------------------------------

tile_layer = "tile_layer"

arcpy.management.MakeFeatureLayer(
    TILE_GRID,
    tile_layer
)


# -------------------------------------------------------------------
# Select tiles intersecting AOI
# -------------------------------------------------------------------

arcpy.AddMessage(f"Selecting tiles intersecting {AOI}")

arcpy.management.SelectLayerByLocation(
    tile_layer,
    "INTERSECT",
    AOI,
    selection_type="NEW_SELECTION"
)


# -------------------------------------------------------------------
# Selected rows -> pandas dataframe
# This makes a dataframe of just the aws urls.
# -------------------------------------------------------------------

df_urls = pd.DataFrame(
    [row[0] for row in arcpy.da.SearchCursor(tile_layer, [URL_FIELD])],
    columns=[URL_FIELD]
)

arcpy.AddMessage(f"Found {len(df_urls)} tiles")


# -------------------------------------------------------------------
# Async download settings
# 2 megabytes seems like a reasonable size.  Orthos can be up to 
# 1 gb.
# -------------------------------------------------------------------

CHUNK_SIZE_MB = 2
CHUNK_SIZE = CHUNK_SIZE_MB * 1024 * 1024

MAX_CONCURRENT_DOWNLOADS = int(os.cpu_count() * 0.75)


# -------------------------------------------------------------------
# Download function
# -------------------------------------------------------------------


def download_file(url, folder, chunk_size=CHUNK_SIZE):
    parsed = urlparse(url)
    filename = Path(parsed.path).name
    out_path = folder / filename

    if out_path.exists():
        arcpy.AddMessage(f"Skipping existing file: {filename}")
        return

    arcpy.AddMessage(f"Downloading: {filename}")

    with requests.get(url, stream=True, timeout=1800) as response:
        response.raise_for_status()

        with open(out_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)

    arcpy.AddMessage(f"Finished: {filename}")


# -------------------------------------------------------------------
# Main async runner
# -------------------------------------------------------------------

def main():
    
    with ThreadPoolExecutor(max_workers=12) as executor:
        executor.map(
            lambda url: download_file(url, DOWNLOAD_FOLDER),
            df_urls[URL_FIELD]
        )
        


# -------------------------------------------------------------------
# Run downloads
# -------------------------------------------------------------------

if __name__ == "__main__":
    main()

arcpy.AddMessage("Downloads complete")
