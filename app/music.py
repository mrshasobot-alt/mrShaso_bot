from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from urllib.parse import quote
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class TrackPreview:
    title: str
    artist: str
    preview_url: str


def _search_itunes(query: str) -> TrackPreview | None:
    url = (
        "https://itunes.apple.com/search?term="
        f"{quote(query)}&media=music&entity=song&limit=1"
    )
    request = Request(url, headers={"User-Agent": "mrShaso-bot/1.0"})
    with urlopen(request, timeout=10) as response:
        payload = json.load(response)

    result = payload.get("results", [{}])[0]
    preview_url = result.get("previewUrl")
    if not preview_url:
        return None

    return TrackPreview(
        title=result.get("trackName", query),
        artist=result.get("artistName", "Unknown artist"),
        preview_url=preview_url,
    )


async def find_track_preview(query: str) -> TrackPreview | None:
    if not query.strip():
        return None
    return await asyncio.to_thread(_search_itunes, query.strip())
