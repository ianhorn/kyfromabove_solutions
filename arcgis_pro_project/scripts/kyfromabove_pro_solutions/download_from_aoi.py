"""

Author: Ian Horn
Date: May 19, 2026

    1. Select an area of interest
    2. Select intersecting tiles
    3. Download imagery

"""

import os
from pathlib import Path
from urllib.parse import urlparse
import asyncio

import arcpy
import pandas as pd
import aiohttp


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

We need to make sure the TILE_GRID layer is something pro 
can work with.
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
This makes a dataframe of just the aws urls.
# -------------------------------------------------------------------

df_urls = pd.DataFrame(
    [row[0] for row in arcpy.da.SearchCursor(tile_layer, [URL_FIELD])],
    columns=[URL_FIELD]
)

arcpy.AddMessage(f"Found {len(df_urls)} tiles")


# -------------------------------------------------------------------
# Async download settings
2 megabytes seems like a reasonable size.  Orthos can be up to 
1 gb.
# -------------------------------------------------------------------

CHUNK_SIZE_MB = 2
CHUNK_SIZE = CHUNK_SIZE_MB * 1024 * 1024

MAX_CONCURRENT_DOWNLOADS = int(os.cpu_count() * 0.75)
SEM = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)


# -------------------------------------------------------------------
# Download function
# -------------------------------------------------------------------

async def download_file(session, url, folder, chunk_size=CHUNK_SIZE):
    async with SEM:
        parsed = urlparse(url)
        filename = Path(parsed.path).name
        out_path = folder / filename

        # Skip existing files
        if out_path.exists():
            arcpy.AddMessage(f"Skipping existing file: {filename}")
            return

        arcpy.AddMessage(f"Downloading: {filename}")

        async with session.get(url) as response:
            response.raise_for_status()

            async with aiofiles.open(out_path, "wb") as f:
                async for chunk in response.content.iter_chunked(chunk_size):
                    await f.write(chunk)

        arcpy.AddMessage(f"Finished: {filename}")


# -------------------------------------------------------------------
# Main async runner
# -------------------------------------------------------------------

async def main():

    timeout = aiohttp.ClientTimeout(total=60 * 30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        tasks = [
            download_file(
                session,
                url,
                DOWNLOAD_FOLDER
            )
            for url in df_urls[URL_FIELD]
        ]
        await asyncio.gather(*tasks)


# -------------------------------------------------------------------
# Run downloads
# -------------------------------------------------------------------

asyncio.run(main())

arcpy.AddMessage("Downloads complete")