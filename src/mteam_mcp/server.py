"""FastMCP stdio server compatible with Hermes Agent."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from fastmcp import FastMCP

from .client import MTeamClient


mcp = FastMCP(
    "mteam-mcp",
    instructions=(
        "Search and inspect torrents on M-Team. "
        "Only call download_torrent when the user explicitly asks to download a torrent file. "
        "Never expose API keys or temporary download tokens."
    ),
)


@lru_cache(maxsize=1)
def _client() -> MTeamClient:
    return MTeamClient.from_env()


@mcp.tool
def search_torrents(
    keyword: str = "",
    mode: str = "normal",
    page_number: int = 1,
    page_size: int = 20,
    visible: int | None = 1,
    categories: list[str] | None = None,
    discount: str | None = None,
    video_codecs: list[str] | None = None,
    audio_codecs: list[str] | None = None,
) -> dict[str, Any]:
    """Search M-Team torrents.

    Args:
        keyword: Keyword, IMDb URL, or Douban URL. Empty text lists matching items.
        mode: M-Team search mode, normally ``normal`` or ``adult``.
        page_number: One-based result page.
        page_size: Number of results, from 1 to 100.
        visible: 1 for active torrents, 2 for dead torrents, or null for no filter.
        categories: Optional M-Team category IDs.
        discount: Optional discount such as FREE, PERCENT_50, or PERCENT_70.
        video_codecs: Optional video codec filters.
        audio_codecs: Optional audio codec filters.
    """
    return _client().search_torrents(
        keyword=keyword,
        mode=mode,
        page_number=page_number,
        page_size=page_size,
        visible=visible,
        categories=categories,
        discount=discount,
        video_codecs=video_codecs,
        audio_codecs=audio_codecs,
    )


@mcp.tool
def get_torrent_detail(torrent_id: str) -> dict[str, Any]:
    """Get the metadata and tracker status for one numeric M-Team torrent ID."""
    return _client().get_torrent_detail(torrent_id)


@mcp.tool
def download_torrent(torrent_id: str) -> dict[str, Any]:
    """Download a .torrent file after the user explicitly requests it.

    The temporary M-Team token remains internal. The result contains only the
    local saved path, torrent ID, and number of bytes written.
    """
    return _client().download_torrent(torrent_id)


def main() -> None:
    """Run the MCP server over stdio, which Hermes Agent supports natively."""
    mcp.run()


if __name__ == "__main__":
    main()
