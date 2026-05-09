# OpenRouter Rankings Data Fetcher

自动获取 OpenRouter 排行榜数据并保存为 JSON 文件。

## 功能

- 自动抓取 OpenRouter 排行榜页面的数据
- 支持获取 Top Apps 和 Model Rankings
- 支持不同时间周期：日、周、月
- GitHub Actions 自动定时执行

## 数据目录结构

```
data/
├── top_apps/
│   ├── 2026-05-09.json      # Top Apps 日数据
│   ├── 2026-05-10.json
│   └── ...
├── models/
│   ├── 2026-05-09.json      # Model Rankings 日数据
│   └── ...
```

## 使用方法

### 本地运行

```bash
# 安装依赖
pip install requests

# 获取所有数据 (默认周数据)
python fetch_openrouter_data.py

# 指定日期
python fetch_openrouter_data.py --date 2026-05-09

# 只获取 Top Apps
python fetch_openrouter_data.py --section apps

# 只获取 Model Rankings
python fetch_openrouter_data.py --section models

# 指定时间周期
python fetch_openrouter_data.py --period day    # 今日
python fetch_openrouter_data.py --period week    # 本周 (默认)
python fetch_openrouter_data.py --period month   # 本月

# 指定输出目录
python fetch_openrouter_data.py --output-dir ./data
```

### GitHub Actions

项目已配置 GitHub Actions，会自动：

1. **每日定时执行** - 每天 UTC 0:00 (北京时间 8:00) 自动获取数据
2. **提交数据** - 自动将新数据提交到仓库
3. **支持手动触发** - 可通过 Actions 页面手动运行

#### 手动触发选项

- `date`: 指定日期 (YYYY-MM-DD)
- `section`: 获取哪部分数据 (`all`, `apps`, `models`)
- `period`: 时间周期 (`day`, `week`, `month`)

## 数据格式

### Top Apps JSON 结构

```json
{
  "source": "https://openrouter.ai/rankings",
  "section": "Top Apps",
  "subsection": "Day (Today)",
  "extracted_at": "2026-05-09T00:00:00.000000",
  "period": "day",
  "description": "Top AI applications and agents ranked by token usage on OpenRouter",
  "total_apps": 20,
  "apps": [
    {
      "rank": 1,
      "app_id": 2725608,
      "total_tokens": 245409466529,
      "total_requests": 4630643,
      "app": {
        "title": "OpenClaw",
        "slug": "openclaw",
        "description": "OpenClaw is an open-source AI agent...",
        "origin_url": "https://openclaw.ai/",
        "categories": ["personal-agent", "cli-agent"]
      }
    }
  ]
}
```

## 技术说明

OpenRouter 使用 Next.js 构建，排行榜数据通过服务端渲染 (SSR) 嵌入在 HTML 中。
数据位于页面源码的 `rankMap` 字段，包含 `day`、`week`、`month` 三个时间段的使用数据。

## License

MIT