from mteam_mcp.server import _format_torrent_detail_markdown


def test_formats_torrent_detail_as_ai_readable_markdown() -> None:
    markdown = _format_torrent_detail_markdown(
        {
            "id": "1125330",
            "name": "The Dark Knight | 2160p",
            "description": "蝙蝠侠：黑暗骑士",
            "category": "401",
            "size_bytes": 19048123801,
            "file_count": 1,
            "created_at": "2026-01-29 15:16:42",
            "labels": ["中字", "4k", "hdr10"],
            "seeders": 17,
            "leechers": 0,
            "completed": 71,
            "discount": "PERCENT_50",
            "discount_end_at": "2026-07-12 00:00:00",
            "visible": True,
            "banned": False,
            "imdb": "https://www.imdb.com/title/tt0468569/",
            "imdb_rating": "9.1",
            "douban": "https://movie.douban.com/subject/1851857/",
            "douban_rating": "9.2",
        }
    )

    assert markdown.startswith("# M-Team 种子详情")
    assert "The Dark Knight \\| 2160p" in markdown
    assert "| 种子 ID | `1125330` |" in markdown
    assert "17.74 GiB" in markdown
    assert "| 17 | 0 | 71 | 是 | 否 |" in markdown
    assert "[https://www.imdb.com/title/tt0468569/]" in markdown
    assert '`{"torrent_id": "1125330"}`' in markdown
    assert "外部元数据" in markdown


def test_omits_invalid_external_links() -> None:
    markdown = _format_torrent_detail_markdown(
        {
            "id": "1",
            "name": "Example",
            "imdb": "javascript:alert(1)",
            "douban": None,
        }
    )

    assert "## 外部链接" not in markdown
    assert "javascript:" not in markdown
