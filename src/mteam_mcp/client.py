"""Small, typed client for the M-Team API used by the MCP tools."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

import httpx


class MTeamError(RuntimeError):
    """A safe error raised for M-Team API or download failures."""


_INVALID_FILENAME = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_TORRENT_ID = re.compile(r"^[0-9]{1,20}$")


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_filename(value: str, fallback: str) -> str:
    value = _INVALID_FILENAME.sub("", value).strip().strip(".")
    value = re.sub(r"\s+", ".", value)
    value = value[:180].rstrip(".")
    return value or fallback


def _filename_from_disposition(header: str | None) -> str | None:
    if not header:
        return None
    utf8_match = re.search(r"filename\*=UTF-8''([^;]+)", header, flags=re.IGNORECASE)
    if utf8_match:
        return unquote(utf8_match.group(1)).strip('"')
    plain_match = re.search(r'filename="?([^";]+)"?', header, flags=re.IGNORECASE)
    return plain_match.group(1).strip() if plain_match else None


class MTeamClient:
    """Synchronous client for M-Team search, detail and torrent download APIs."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.m-team.cc/api",
        download_dir: str | Path = "~/.hermes/downloads/mteam",
        timeout: float = 30.0,
        max_torrent_bytes: int = 32 * 1024 * 1024,
        api_transport: httpx.BaseTransport | None = None,
        download_transport: httpx.BaseTransport | None = None,
    ) -> None:
        api_key = api_key.strip()
        if not api_key:
            raise MTeamError("MTEAM_API_KEY is not configured")
        if timeout <= 0:
            raise MTeamError("MTEAM_TIMEOUT must be greater than zero")
        if max_torrent_bytes <= 0:
            raise MTeamError("MTEAM_MAX_TORRENT_BYTES must be greater than zero")

        self.base_url = base_url.rstrip("/")
        self.download_dir = Path(download_dir).expanduser().resolve()
        self.max_torrent_bytes = max_torrent_bytes
        self._api = httpx.Client(
            base_url=self.base_url,
            headers={"Accept": "application/json", "x-api-key": api_key},
            timeout=timeout,
            transport=api_transport,
        )
        # Intentionally omit x-api-key for temporary download URLs. This avoids
        # leaking the API key if M-Team redirects to another host.
        self._download = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            transport=download_transport,
        )

    @classmethod
    def from_env(cls) -> "MTeamClient":
        """Construct a client from environment variables used by Hermes."""
        try:
            timeout = float(os.environ.get("MTEAM_TIMEOUT", "30"))
            max_bytes = int(os.environ.get("MTEAM_MAX_TORRENT_BYTES", str(32 * 1024 * 1024)))
        except ValueError as exc:
            raise MTeamError("MTEAM_TIMEOUT and MTEAM_MAX_TORRENT_BYTES must be numeric") from exc

        return cls(
            api_key=os.environ.get("MTEAM_API_KEY", ""),
            base_url=os.environ.get("MTEAM_API_BASE", "https://api.m-team.cc/api"),
            download_dir=os.environ.get("MTEAM_DOWNLOAD_DIR", "~/.hermes/downloads/mteam"),
            timeout=timeout,
            max_torrent_bytes=max_bytes,
        )

    def close(self) -> None:
        self._api.close()
        self._download.close()

    def __enter__(self) -> "MTeamClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _post(self, path: str, *, json: dict[str, Any] | None = None, data: dict[str, Any] | None = None) -> Any:
        try:
            response = self._api.post(path, json=json, data=data)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise MTeamError(f"M-Team HTTP error: {exc.response.status_code}") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise MTeamError("M-Team request failed or returned invalid JSON") from exc

        if not isinstance(payload, dict):
            raise MTeamError("M-Team returned an unexpected response")

        code = str(payload.get("code", ""))
        message = str(payload.get("message", "Unknown error"))
        success = code == "0" or (not code and message.upper() == "SUCCESS")
        if not success:
            raise MTeamError(f"M-Team API error {code or '?'}: {message}")
        return payload.get("data")

    @staticmethod
    def _validate_torrent_id(torrent_id: str | int) -> str:
        value = str(torrent_id).strip()
        if not _TORRENT_ID.fullmatch(value):
            raise MTeamError("torrent_id must contain only 1 to 20 digits")
        return value

    @staticmethod
    def _normalise_item(item: dict[str, Any]) -> dict[str, Any]:
        status = item.get("status") if isinstance(item.get("status"), dict) else {}
        return {
            "id": str(item.get("id", "")),
            "name": item.get("name") or item.get("title") or "",
            "description": item.get("smallDescr") or "",
            "category": item.get("category"),
            "size_bytes": _as_int(item.get("size")),
            "file_count": _as_int(item.get("numfiles")),
            "created_at": item.get("createdDate"),
            "labels": item.get("labelsNew") or [],
            "imdb": item.get("imdb"),
            "imdb_rating": item.get("imdbRating"),
            "douban": item.get("douban"),
            "douban_rating": item.get("doubanRating"),
            "seeders": _as_int(status.get("seeders")),
            "leechers": _as_int(status.get("leechers")),
            "completed": _as_int(status.get("timesCompleted")),
            "discount": status.get("discount"),
            "discount_end_at": status.get("discountEndTime"),
            "visible": status.get("visible"),
            "banned": status.get("banned"),
        }

    def search_torrents(
        self,
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
        """Search torrents and return a stable, model-friendly response."""
        if page_number < 1:
            raise MTeamError("page_number must be at least 1")
        if not 1 <= page_size <= 100:
            raise MTeamError("page_size must be between 1 and 100")
        if visible not in (None, 1, 2):
            raise MTeamError("visible must be null, 1 (active), or 2 (dead)")
        if not mode.strip():
            raise MTeamError("mode cannot be empty")

        body: dict[str, Any] = {
            "keyword": keyword,
            "mode": mode,
            "pageNumber": page_number,
            "pageSize": page_size,
        }
        if visible is not None:
            body["visible"] = visible
        if categories:
            body["categories"] = [str(value) for value in categories]
        if discount:
            body["discount"] = discount
        if video_codecs:
            body["videoCodecs"] = video_codecs
        if audio_codecs:
            body["audioCodecs"] = audio_codecs

        payload = self._post("/torrent/search", json=body)
        if isinstance(payload, dict):
            raw_items = payload.get("data") or payload.get("list") or payload.get("torrents") or []
            total = _as_int(payload.get("total") or payload.get("totalCount"), len(raw_items))
            total_pages = _as_int(payload.get("totalPages"))
            returned_page = _as_int(payload.get("pageNumber"), page_number)
            returned_size = _as_int(payload.get("pageSize"), page_size)
        elif isinstance(payload, list):
            raw_items = payload
            total = len(raw_items)
            total_pages = 1
            returned_page = page_number
            returned_size = page_size
        else:
            raise MTeamError("M-Team search returned an unexpected response")

        items = [self._normalise_item(item) for item in raw_items if isinstance(item, dict)]
        return {
            "query": keyword,
            "mode": mode,
            "page_number": returned_page,
            "page_size": returned_size,
            "total": total,
            "total_pages": total_pages,
            "items": items,
        }

    def get_torrent_detail(self, torrent_id: str | int) -> dict[str, Any]:
        """Return normalised details for one torrent ID."""
        validated_id = self._validate_torrent_id(torrent_id)
        payload = self._post("/torrent/detail", data={"id": validated_id})
        if not isinstance(payload, dict):
            raise MTeamError("M-Team detail returned an unexpected response")
        item = self._normalise_item(payload)
        if not item["id"]:
            item["id"] = validated_id
        return item

    def _generate_download_url(self, torrent_id: str) -> str:
        payload = self._post("/torrent/genDlToken", data={"id": torrent_id})
        if not isinstance(payload, str) or not payload.strip():
            raise MTeamError("M-Team did not return a download URL")
        parsed = urlparse(payload)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise MTeamError("M-Team returned an invalid download URL")
        return payload

    def download_torrent(self, torrent_id: str | int) -> dict[str, Any]:
        """Download one .torrent file atomically into the configured directory."""
        validated_id = self._validate_torrent_id(torrent_id)
        download_url = self._generate_download_url(validated_id)

        fallback_name = validated_id
        try:
            detail = self.get_torrent_detail(validated_id)
            fallback_name = str(detail.get("name") or validated_id)
        except MTeamError:
            # The download can still succeed even if the optional name lookup fails.
            pass

        self.download_dir.mkdir(parents=True, exist_ok=True)

        try:
            with self._download.stream("GET", download_url) as response:
                response.raise_for_status()
                disposition_name = _filename_from_disposition(response.headers.get("content-disposition"))
                raw_name = disposition_name or f"[M-TEAM]{fallback_name}.torrent"
                if not raw_name.lower().endswith(".torrent"):
                    raw_name += ".torrent"
                filename = _safe_filename(raw_name, f"{validated_id}.torrent")
                output_path = (self.download_dir / filename).resolve()
                if output_path.parent != self.download_dir:
                    raise MTeamError("Refusing to write outside MTEAM_DOWNLOAD_DIR")

                temporary_path = output_path.with_suffix(output_path.suffix + ".part")
                written = 0
                try:
                    with temporary_path.open("wb") as handle:
                        for chunk in response.iter_bytes(128 * 1024):
                            written += len(chunk)
                            if written > self.max_torrent_bytes:
                                raise MTeamError("Torrent file exceeds MTEAM_MAX_TORRENT_BYTES")
                            handle.write(chunk)
                    temporary_path.replace(output_path)
                except Exception:
                    temporary_path.unlink(missing_ok=True)
                    raise
        except httpx.HTTPStatusError as exc:
            raise MTeamError(f"Torrent download HTTP error: {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise MTeamError("Torrent download failed") from exc

        return {
            "torrent_id": validated_id,
            "saved_path": str(output_path),
            "bytes_written": written,
        }
