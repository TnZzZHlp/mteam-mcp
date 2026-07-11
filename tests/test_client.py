from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from mteam_mcp.client import MTeamClient, MTeamError


def json_response(data: object, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code,
        headers={"content-type": "application/json"},
        content=json.dumps(data).encode(),
    )


def test_search_normalises_results(tmp_path: Path) -> None:
    def api_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/torrent/search")
        assert request.headers["x-api-key"] == "secret"
        body = json.loads(request.content)
        assert body["keyword"] == "test"
        return json_response(
            {
                "code": "0",
                "message": "SUCCESS",
                "data": {
                    "pageNumber": "1",
                    "pageSize": "20",
                    "total": "1",
                    "totalPages": "1",
                    "data": [
                        {
                            "id": "123",
                            "name": "Example",
                            "size": "1024",
                            "labelsNew": ["4k"],
                            "status": {"seeders": "7", "leechers": "2", "discount": "FREE"},
                        }
                    ],
                },
            }
        )

    client = MTeamClient(
        "secret",
        download_dir=tmp_path,
        api_transport=httpx.MockTransport(api_handler),
    )
    result = client.search_torrents("test")
    assert result["total"] == 1
    assert result["items"][0]["size_bytes"] == 1024
    assert result["items"][0]["seeders"] == 7
    assert result["items"][0]["leechers"] == 2
    assert result["items"][0]["id"] == "123"
    assert result["items"][0]["discount"] == "FREE"
    client.close()


def test_api_error_does_not_include_key(tmp_path: Path) -> None:
    def api_handler(_: httpx.Request) -> httpx.Response:
        return json_response({"code": "403", "message": "Forbidden", "data": None})

    client = MTeamClient(
        "super-secret-key",
        download_dir=tmp_path,
        api_transport=httpx.MockTransport(api_handler),
    )
    with pytest.raises(MTeamError) as error:
        client.search_torrents("x")
    assert "super-secret-key" not in str(error.value)
    client.close()


def test_download_saves_torrent_without_sending_api_key_to_download_host(tmp_path: Path) -> None:
    calls: list[httpx.Request] = []

    def api_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/torrent/genDlToken"):
            return json_response(
                {"code": "0", "message": "SUCCESS", "data": "https://download.example/file"}
            )
        if request.url.path.endswith("/torrent/detail"):
            return json_response(
                {"code": "0", "message": "SUCCESS", "data": {"id": "123", "name": "Demo Name"}}
            )
        raise AssertionError(request.url)

    def download_handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            headers={"content-disposition": 'attachment; filename="demo.torrent"'},
            content=b"d4:infod4:name4:teste",
        )

    client = MTeamClient(
        "secret",
        download_dir=tmp_path,
        api_transport=httpx.MockTransport(api_handler),
        download_transport=httpx.MockTransport(download_handler),
    )
    result = client.download_torrent("123")
    saved = Path(result["saved_path"])
    assert saved.name == "demo.torrent"
    assert saved.read_bytes() == b"d4:infod4:name4:teste"
    assert result["bytes_written"] == len(saved.read_bytes())
    assert "x-api-key" not in calls[0].headers
    client.close()


@pytest.mark.parametrize("torrent_id", ["../1", "abc", "", "1/2"])
def test_rejects_invalid_torrent_id(tmp_path: Path, torrent_id: str) -> None:
    client = MTeamClient("secret", download_dir=tmp_path)
    with pytest.raises(MTeamError, match="digits"):
        client.get_torrent_detail(torrent_id)
    client.close()


def test_validates_pagination(tmp_path: Path) -> None:
    client = MTeamClient("secret", download_dir=tmp_path)
    with pytest.raises(MTeamError, match="page_size"):
        client.search_torrents(page_size=101)
    client.close()
