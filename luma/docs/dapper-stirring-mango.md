# 动画元数据增量处理 Pipeline - 架构设计文档

## 上下文

这是一个数据工程面试题项目，需要构建一个可靠的、支持断点恢复的端到端数据处理 pipeline。项目将从 MyAnimeList (MAL) 获取动画元数据，进行质量检查和 Wikidata 匹配，存储到 SQLite 并支持导出。

**核心考察点**：增量和断点恢复设计（最高优先级）

---

## 项目目录结构

```
luma/
├── pyproject.toml                 # uv 项目配置
├── README.md                      # 项目文档
├── ARCHITECTURE.md                # 架构设计文档
├── cli.py                         # CLI 入口点
│
├── src/
│   └── luma/
│       ├── __init__.py
│       ├── __main__.py            # 支持 python -m luma
│       │
│       ├── core/                  # 核心业务逻辑
│       │   ├── __init__.py
│       │   ├── fetch.py           # 数据获取 (Jikan API)
│       │   ├── quality.py         # 质量检查
│       │   ├── match.py           # Wikidata 匹配
│       │   └── storage.py         # 数据库操作
│       │
│       ├── pipeline/              # Pipeline 编排
│       │   ├── __init__.py
│       │   ├── orchestrator.py   # 流程编排
│       │   ├── checkpoint.py     # 检查点管理
│       │   └── reporter.py       # 报告生成
│       │
│       ├── infrastructure/        # 基础设施
│       │   ├── __init__.py
│       │   ├── rate_limiter.py   # API 速率限制
│       │   ├── database.py       # 数据库连接
│       │   └── http_client.py    # HTTP 客户端
│       │
│       ├── models/                # 数据模型 (Pydantic)
│       │   ├── __init__.py
│       │   ├── anime.py          # 动画数据模型
│       │   ├── quality.py        # 质量检查模型
│       │   ├── match.py          # 匹配结果模型
│       │   └── checkpoint.py     # 检查点模型
│       │
│       ├── config/                # 配置管理
│       │   ├── __init__.py
│       │   ├── settings.py       # 配置类
│       │   └── constants.py      # 常量定义
│       │
│       └── utils/                 # 工具函数
│           ├── __init__.py
│           ├── logging.py        # 日志配置
│           └── helpers.py        # 辅助函数
│
├── data/                          # 数据目录
│   ├── .gitkeep
│   ├── anime.db                   # SQLite 数据库
│   └── checkpoint.json            # 检查点文件
│
├── output/                        # 导出目录
│   └── .gitkeep
│
├── tests/                         # 测试目录
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_fetch.py
│   ├── test_quality.py
│   ├── test_match.py
│   ├── test_checkpoint.py
│   └── test_pipeline.py
│
└── docs/                          # 文档目录
    ├── design.md                  # 设计决策
    ├── checkpoint_strategy.md     # 检查点策略详解
    └── testing.md                 # 测试文档
```

---

## 核心模块设计

### 1. 数据获取模块 (`core/fetch.py`)

```python
class AnimeFetcher:
    """从 Jikan API 获取动画数据"""

    async def fetch_anime(self, anime_id: int) -> Optional[Anime]:
        """获取单个动画数据"""

    async def fetch_anime_batch(self, anime_ids: List[int], batch_size: int = 10) -> List[Anime]:
        """批量获取动画数据"""

    async def fetch_anime_range(self, start_id: int, end_id: int) -> AsyncIterator[Anime]:
        """获取 ID 范围内的动画（异步迭代器）"""
```

### 2. 质量检查模块 (`core/quality.py`)

**三条核心规则**：
1. **字段完整性**：检查必需字段是否存在
2. **值域验证**：验证评分(1-10)、集数(1-2000)、年份(1900-至今+5)
3. **标题格式**：拒绝空标题、TBA/N/A 等

```python
class QualityChecker:
    """质量检查器"""

    def check(self, anime: Anime) -> QualityResult:
        """执行所有质量检查"""
```

### 3. Wikidata 匹配模块 (`core/match.py`)

**匹配策略**：
1. **精确 ID 匹配** (confidence ≥ 0.9)：使用 MAL ID 属性
2. **精确标题+年份** (confidence ≥ 0.9)
3. **模糊标题** (confidence 0.5-0.9)：使用 RapidFuzz
4. **多字段组合** (confidence 0.5-0.9)：标题+集数+年份

```python
class WikidataMatcher:
    def match(self, anime: Anime) -> List[MatchResult]:
        """执行匹配，返回候选列表（按置信度排序）"""

    def find_best_match(self, anime: Anime) -> Optional[MatchResult]:
        """返回最佳匹配（confidence >= 0.5）"""
```

### 4. 检查点管理 (`pipeline/checkpoint.py`)

**检查点状态结构**：
```python
@dataclass
class CheckpointState:
    checkpoint_id: str                    # 唯一 ID
    timestamp: datetime                   # 检查点时间

    # 处理范围
    start_id: int
    end_id: int
    total_count: int

    # 进度追踪
    processed_ids: Set[int]               # 已完成
    in_progress_ids: Set[int]             # 进行中
    pending_ids: Set[int]                 # 待处理

    # 当前阶段
    current_stage: PipelineStage          # fetch/quality/match/store
    current_batch_index: int              # 当前批次

    # 统计信息
    stats: PipelineStats

    # 错误信息
    errors: List[ProcessingError]
```

**保存时机**：
- 每个批次处理完成后
- 每个阶段切换前
- 异常发生时

**幂等性保证**：
- 使用"写入临时文件 + 原子重命名"模式
- 数据库使用 UPSERT 防止重复

### 5. Pipeline 编排器 (`pipeline/orchestrator.py`)

```python
class PipelineOrchestrator:
    """Pipeline 编排器"""

    async def run(self, start_id: int, end_id: int, resume: bool = False) -> PipelineReport:
        """执行 pipeline"""
```

**处理流程**：
1. 初始化（恢复或新建）
2. 按批次处理动画
3. 对每个动画执行：获取 → 质检 → 匹配 → 存储
4. 定期保存检查点
5. 生成报告

---

## 数据库 Schema 设计

```sql
-- 动画元数据表
CREATE TABLE anime (
    id INTEGER PRIMARY KEY,
    mal_id INTEGER UNIQUE NOT NULL,
    title TEXT NOT NULL,
    title_japanese TEXT,
    title_english TEXT,
    episodes INTEGER,
    score REAL,
    year INTEGER,
    type TEXT,
    source TEXT,
    studios TEXT,
    genres TEXT,
    synopsis TEXT,
    processing_status TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 质量检查结果表
CREATE TABLE quality_checks (
    id INTEGER PRIMARY KEY,
    anime_id INTEGER NOT NULL,
    passed BOOLEAN NOT NULL,
    overall_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (anime_id) REFERENCES anime(id)
);

-- Wikidata 匹配结果表
CREATE TABLE matches (
    id INTEGER PRIMARY KEY,
    anime_id INTEGER NOT NULL UNIQUE,
    wikidata_id TEXT,
    wikidata_label TEXT,
    confidence REAL NOT NULL,
    match_method TEXT NOT NULL,
    match_metadata TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (anime_id) REFERENCES anime(id)
);

-- 处理错误表
CREATE TABLE processing_errors (
    id INTEGER PRIMARY KEY,
    anime_id INTEGER,
    stage TEXT NOT NULL,
    error_type TEXT NOT NULL,
    error_message TEXT NOT NULL,
    stack_trace TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 并发控制策略

**三层控制**：
1. **并发数限制**：`asyncio.Semaphore(max_concurrent=10)`
2. **速率限制**：Token Bucket 算法，Jikan API 限制 3 req/s
3. **批量处理**：每批处理 10 个，完成后保存检查点

```python
class RateLimiter:
    """基于 Token Bucket 的速率限制器"""

    def __init__(self, rate: float = 3.0, burst: int = 5):
        self.rate = rate
        self.burst = burst
```

---

## CLI 命令设计

```bash
# 运行 pipeline
python cli.py run [OPTIONS]
  --start-id INTEGER      起始 MAL ID
  --end-id INTEGER        结束 MAL ID
  --limit INTEGER         处理数量
  --batch-size INTEGER    批次大小（默认：10）
  --concurrent INTEGER    并发数（默认：5）
  --rate-limit FLOAT      API 速率限制（默认：3）

# 从检查点恢复
python cli.py resume

# 导出数据
python cli.py export [OPTIONS]
  --output PATH           输出文件路径（默认：output/anime.jsonl）
  --filter TEXT           过滤条件（matched/unmatched/all）

# 查看状态
python cli.py status

# 清除检查点
python cli.py checkpoint clear
```

---

## 依赖配置 (pyproject.toml)

```toml
[project]
name = "luma"
version = "0.1.0"
description = "Anime metadata incremental processing pipeline"
requires-python = ">=3.11"
dependencies = [
    "click>=8.1.0",        # CLI 框架
    "httpx>=0.24.0",       # 异步 HTTP 客户端
    "pydantic>=2.0.0",     # 数据验证
    "aiosqlite>=0.19.0",   # 异步 SQLite
    "rapidfuzz>=3.0.0",    # 模糊匹配
    "python-dotenv>=1.0.0", # 环境变量
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
    "pytest-cov>=4.0.0",
    "black>=23.0.0",
    "ruff>=0.1.0",
]
```

---

## 实现优先级

### P0 - 核心功能（必须实现）
- `src/luma/core/fetch.py` - 数据获取
- `src/luma/core/quality.py` - 质量检查
- `src/luma/pipeline/checkpoint.py` - 检查点管理
- `src/luma/pipeline/orchestrator.py` - 流程编排
- `src/luma/infrastructure/rate_limiter.py` - 速率限制

### P1 - 重要功能（应该实现）
- `src/luma/core/match.py` - Wikidata 匹配
- `src/luma/core/storage.py` - 数据存储
- `src/luma/models/anime.py` - 数据模型
- `cli.py` - CLI 入口

### P2 - 支持功能（可以简化）
- `src/luma/pipeline/reporter.py` - 报告生成
- `src/luma/config/settings.py` - 配置管理
- `src/luma/utils/logging.py` - 日志配置

---

## 验收测试场景

**断点恢复测试**：
1. 运行 pipeline 处理前 1000 条数据
2. 在匹配阶段 kill 进程
3. 重启 pipeline 使用 `--resume`
4. 验证：从断点继续，不重复处理

---

## 关键文件清单

需要创建/修改的核心文件：

1. `/Users/zhihu/output/github/interview-demos/luma/pyproject.toml` - 项目配置
2. `/Users/zhihu/output/github/interview-demos/luma/cli.py` - CLI 入口
3. `/Users/zhihu/output/github/interview-demos/luma/src/luma/__init__.py` - 包初始化
4. `/Users/zhihu/output/github/interview-demos/luma/src/luma/core/fetch.py` - 数据获取
5. `/Users/zhihu/output/github/interview-demos/luma/src/luma/core/quality.py` - 质量检查
6. `/Users/zhihu/output/github/interview-demos/luma/src/luma/core/storage.py` - 数据存储
7. `/Users/zhihu/output/github/interview-demos/luma/src/luma/pipeline/checkpoint.py` - 检查点管理
8. `/Users/zhihu/output/github/interview-demos/luma/src/luma/pipeline/orchestrator.py` - 流程编排
9. `/Users/zhihu/output/github/interview-demos/luma/src/luma/infrastructure/rate_limiter.py` - 速率限制
10. `/Users/zhihu/output/github/interview-demos/luma/src/luma/infrastructure/database.py` - 数据库连接
11. `/Users/zhihu/output/github/interview-demos/luma/src/luma/models/anime.py` - 数据模型
