# mteam-mcp

面向 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 的 M-Team MCP Server。通过标准 stdio MCP 提供种子查询、详情查看和 `.torrent` 文件下载功能。

## 工具

| MCP 工具 | 功能 |
|---|---|
| `search_torrents` | 按关键词、分区、分类、优惠、编码和存活状态查询种子 |
| `get_torrent_detail` | 根据数字种子 ID 获取详情和做种状态 |
| `download_torrent` | 生成临时下载令牌并将 `.torrent` 文件保存到本地目录 |

下载令牌只在进程内部使用，不会返回给模型。M-Team API Key 仅通过环境变量传入。

## Hermes Agent 配置

需要先安装 [`uv`](https://docs.astral.sh/uv/)。将以下内容加入 Hermes 的 MCP 配置：

```yaml
mcp_servers:
  mteam:
    command: "uvx"
    args:
      - "--from"
      - "git+https://github.com/TnZzZHlp/mteam-mcp.git"
      - "mteam-mcp"
    env:
      MTEAM_API_KEY: "你的 API Key"
      MTEAM_API_BASE: "https://api.m-team.cc/api"
      MTEAM_DOWNLOAD_DIR: "~/.hermes/downloads/mteam"
      MTEAM_TIMEOUT: "30"
    enabled: true
    timeout: 120
    connect_timeout: 30
    supports_parallel_tool_calls: false
    tools:
      include: [search_torrents, get_torrent_detail, download_torrent]
      resources: false
      prompts: false
```

修改后在 Hermes 中执行：

```text
/reload-mcp
```

Hermes 注册后的工具名为：

```text
mcp_mteam_search_torrents
mcp_mteam_get_torrent_detail
mcp_mteam_download_torrent
```

### 使用测试环境

将配置中的 API 地址改为：

```yaml
MTEAM_API_BASE: "https://test2.m-team.cc/api"
```

测试环境和正式环境可能使用不同账号数据或 API Key。

## 本地运行

```bash
git clone https://github.com/TnZzZHlp/mteam-mcp.git
cd mteam-mcp
uv sync
MTEAM_API_KEY='你的 API Key' uv run mteam-mcp
```

也可以复制环境变量模板：

```bash
cp .env.example .env
```

本项目不会自动读取 `.env`。启动前应由 shell、systemd、容器或 Hermes 的 `env` 配置注入变量。

## 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|---|---|---|---|
| `MTEAM_API_KEY` | 是 | 无 | M-Team API Key |
| `MTEAM_API_BASE` | 否 | `https://api.m-team.cc/api` | API 根地址 |
| `MTEAM_DOWNLOAD_DIR` | 否 | `~/.hermes/downloads/mteam` | `.torrent` 保存目录 |
| `MTEAM_TIMEOUT` | 否 | `30` | HTTP 超时秒数 |
| `MTEAM_MAX_TORRENT_BYTES` | 否 | `33554432` | 单个种子文件最大字节数 |

## 查询参数示例

Hermes 可调用：

```json
{
  "keyword": "The Dark Knight",
  "mode": "normal",
  "page_number": 1,
  "page_size": 20,
  "visible": 1,
  "categories": [],
  "discount": "FREE"
}
```

`visible`：

- `1`：活种
- `2`：死种
- `null`：不筛选

## 开发和测试

```bash
uv sync --extra dev
uv run pytest -q
```

## 安全说明

- 不要把真实 API Key 写入仓库、命令历史、日志或聊天内容。
- `download_torrent` 不会把临时下载 URL 返回给模型。
- 临时下载请求不会携带 `x-api-key`，避免重定向到其他域名时泄露密钥。
- 下载采用临时文件后原子替换，并限制最大文件大小。
- 仅用于你有权访问和下载的内容，并遵守站点规则及当地法律。

## License

MIT
