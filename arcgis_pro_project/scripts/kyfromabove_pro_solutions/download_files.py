import aiohttp
import aiofiles
import asyncio
from pathlib import Path
from urllib.parse import urlparse

chunksize_mb = 2
chunk = chunksize_mb * (1024 * 1024)

async def download_file(url, folder, chunk_size=chunk):
    parsed = urlparse(url)
    filename = Path(parsed.path).name

    out_path = folder / filename

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()

            async with aiofiles.open(out_path, "wb") as f:
                async for data in response.content.iter_chunked(chunk_size):
                    await f.write(data)