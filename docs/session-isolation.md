# session 隔离设计记录

> 状态：已实现，跟代码对齐。  
> 用途：记录设计决策与理由，避免下次重新推一遍。

---

## 1. 触发点

跑 eval 的时候，agent 跑出的痕迹会跟用户日常会话混在同一个 `~/.codeagent/session.{json,sql}` 里。两个问题：

- **单 agent 串行**：eval 的会话和主会话同一个文件，模型能区分但**用户分析起来不便**
- **多 agent 并行**：两个进程同时写同一文件，**写入 race + 读取错序 + context 干扰**

> "eval 的会话不能和主会话一样出现在 session.json 里"
>
> "多agent并行是无法避免的"

---

## 2. 设计原则

### 2.1 session 是"独立工作流的物理容器"

| 目的 | 含义 |
|------|------|
| 隔离独立工作流 | 不同任务不互相污染 |
| 防并发串扰 | 写 race、读错序、context 干扰 |
| 限定 resource scope | 工具、数据、配置生效到哪儿 |
| artifact 归属 | 跑出来的东西归这次 run |

**之前我们把它想窄了**——以为只是"切话题降 context"。实际上 session 是**"独立工作流的容器"**，context 隔离只是它一个应用。

### 2.2 检索不能替代 session

哪怕检索 100% 准确，也救不了"两个 session 交错"：

- **协议硬约束**：`tool_use_id` ↔ `tool_result` 必须配对，交错就 400
- **推理线程断**：agent 推理是线性的，**插话就断**
- **文件层 race**：两个进程并发写同一文件

**记忆层 = 检索擅长**。**活儿层 = session 提供**。两者不替代。

### 2.3 决策对比：朴素方案反而最便宜

| 方案 | 检索成本 | 锁成本 | 响应速度 | 并发支持 |
|------|---------|--------|---------|---------|
| A. 全局共用 session，靠检索挑相关 | 高 | 不需要 | 拖慢 | 需要锁 |
| B. 全局共用 session，靠锁串行写 | 不需要 | 中 | 拖慢 | 支持但代价高 |
| C. **每次启动 = 新 session**（采用） | 不需要 | 不需要 | 不拖慢 | 自然支持 |

**C 路线**：把"切分"从**运行时**推到**启动时**，一次决定一次成本；之后推理路径上零额外开销。

---

## 3. 最终方案

> **每次 agent 启动 = 一个新 session。**
> **目录结构：`~/.codeagent/projects/<sanitize-cwd>/<timestamp>/session.json`**

| 元素 | 编码方式 | 例 |
|------|----------|-----|
| 项目目录 | `abs_cwd.replace('/', '-')`（**保留前导 `-`**） | `/home/user/projectA` → `-home-user-projectA` |
| session id | `datetime.now().strftime('%Y-%m-%d-%H%M%S-%f')`（微秒级） | `2026-07-23-114512-345678` |

**为什么是这套**：
- **项目目录不带 hash**：sanitize 后理论碰撞概率几乎为零（`/a/b-c` vs `/a/b/c` 这种要真实存在两个目录才算撞），不需要 sha256 防御性叠加。可读性优先。
- **session id 用微秒时间戳**：可读、字典序就是时间序、并发时几乎不撞（1,000,000/s 唯一）。比 UUID 短 14 字符、比 UUID 直观。
- **不加路径 hash**：可读性是更高优先级。
- **默认新 session**：跨 invocation 切分 + 并发自然支持，不需要锁。

---

## 4. 目录结构

```
~/.codeagent/
├── .migrated_from_cwd              ← 旧版 cwd→home 迁移的 flag（保留，不删）
└── projects/
    └── -home-user-projectA/        ← sanitize 后保留前导 -
        ├── 2026-07-22-211706-198401/   ← 第一次跑（21MB 历史数据，2026-07-22 手动搬过来）
        │   └── session.json
        ├── 2026-07-23-114512-345678/   ← 第二次跑
        │   └── session.json
        └── ...
```

**`mainsession/` 不存在**——它是"最新一次跑"的隐喻，不是物理实体。`--continue` 不实现。

---

## 5. CLI 形状

```bash
# 默认：每次启动 = 新 session（基于微秒时间戳）
python -m agent "fix bug"

# 显式命名（eval、批处理），撞名直接报错
python -m agent --session eval-2026-07-23 "..."
```

**没有 `--continue` / `--resume`**——**暂不做**。要接续上次的对话，**手动复制 timestamp 目录**或者**外部工具**。

| flag | 行为 |
|------|------|
| 无 | 新 timestamp session |
| `--session <name>` | 用确切名字，撞名报错 |

---

## 6. 已决定的点

### 6.1 路径编码（项目目录）

```python
def _project_key(abs_cwd: str) -> str:
    return "".join(
        c if (c.isalnum() or c in "-_.") else "-"
        for c in abs_cwd
    )
```

**不加 hash**。理论碰撞（`/a/b-c` 跟 `/a/b/c` 撞）需要真实存在两个目录——实际不会发生。

### 6.2 session id

```python
def _new_session_id() -> str:
    return _dt.datetime.now().strftime("%Y-%m-%d-%H%M%S-%f")
```

**微秒级时间戳**，格式 `YYYY-MM-DD-HHMMSS-microseconds`。
**例**：`2026-07-23-114512-345678`

**为什么是时间戳不是 UUID**：
- 字典序就是时间序，**目录 ls 一下就看出时间**
- 比 UUID 短 14 字符
- 1,000,000/s 唯一性，并发几乎不撞

### 6.3 session 文件位置

```python
SESSION_FILE = SESSION_DIR / "session.json"
```

**每个 session 一个 `session.json`**。**没有**双写（之前有 json + sql，现在只 json）。

### 6.4 变量 rename

| 旧 | 新 |
|---|---|
| `MEMORY_DIR`  | `SESSION_DIR`  |
| `MEMORY_FILE` | `SESSION_FILE` |

"memory" 一词在 Claude Code 生态里专指"抽出来的事实"（见 `~/.claude/projects/<cwd>/memory/`），用 session 文件名上容易混。

### 6.5 跨 session 可见性

**每个 session 只看见自己的历史**。**默认不跨 session**。

### 6.6 不引入新文件

只动位置和命名。不引入 `events.jsonl`、`meta.json`、`memory/` 等结构。

### 6.7 不需要锁

一个 session 一个进程，从来不并发。锁无意义。

### 6.8 不需要 mainsession

`mainsession/` 不存在。`--continue` 不实现。

### 6.9 不需要迁移代码

旧文件的位置 / 状态由用户**手动管理**。**agent 启动时只管"创建新 session + 写入"，不管"老数据怎么办"**。

---

## 7. 暂不做的事

- 不做跨 session 检索
- 不做 facts 抽取 / memory 层
- 不做云同步
- 不做 session 元数据（created_at、tokens、title 等）
- 不做 sub-agent session 隔离
- 不做 per-session contexts 配置
- 不做文件锁
- 不做 auto-fork
- **不做 `--continue` / `--resume`**

---

## 8. JSON / JSONL 的取舍

**保持 JSON array**，不切 JSONL。理由：
- 性能问题还没撞上（单 session 文件还不算大）
- 切 JSONL 是独立重构（动 `_append_memory` 全部逻辑、迁移格式、改名）
- 切不切是性能优化问题，不是并发安全问题

**触发切 JSONL 的时机**：单 session 文件 > 10MB 或 append 明显卡顿。

---

## 9. 决策日志

- **2026-07-13**：提出 session 隔离需求
- **2026-07-13 ~ 14**：经过 mainsession + auto-fork + 锁等方案迭代
- **2026-07-14**：方案定型"每次启动 = 新 session + --continue"，写入 `docs/session-isolation.md`
- **2026-07-22 ~ 23**：用户重新审视需求
  - 决定**砍掉 `--continue` / `--resume`**（"暂不讨论"）
  - 决定**砍掉路径 hash**（"似乎没用"）
  - 决定**session id 改用时间戳**（"微秒时间戳，方便阅读"）
  - 决定**砍掉迁移代码**（"没有兼容逻辑"）
  - 决定**手动挪历史数据**到新位置
- **2026-07-23**：实现对齐新设计
  - 路径只 sanitize
  - session id 用 `strftime("%Y-%m-%d-%H%M%S-%f")`
  - 只剩 `--session <name>` 一个 flag
  - 没有迁移、没有锁、没有 mainsession
