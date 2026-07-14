# session 隔离设计记录

> 当前状态：方案已定，进入实现前的最后阶段。  
> 用途：记录设计决策与理由，避免下次重新推一遍。

---

## 1. 触发点

跑 eval 的时候，agent 跑出的痕迹会跟用户日常会话混在同一个 `~/.codeagent/session.{json,sql}` 里。两个问题：

- **单 agent 串行**：eval 的会话和主会话同一个文件，**模型能区分但用户分析起来不便**
- **多 agent 并行**：两个进程同时写同一文件，**写入 race + 读取错序 + context 干扰**

用户原话：
> "eval 的会话不能和主会话一样出现在 session.json 里"

> "多agent并行是无法避免的"

---

## 2. 关键洞察

### 2.1 用户的分析

**场景 1：单 agent 串行不同任务**

> "单agent串行时,不同任务的会话会混入,比如eval的会话会混入主会话.这个似乎也没啥的,模型应该能区分出这是两个任务.只是我个人觉得不便于我分析会话."

**结论**：模型能区分，**不是技术必要性**。是**用户分析方便**。

**场景 2：多 agent 并行**

> "多agent并行无法区分上下文.写入有并发问题,读取有多任务乱序,干扰当前会话.而且多agent并行是无法避免的."

**结论**：**协议层硬约束**——`tool_use` ↔ `tool_result` 配对是原子的，两个 session 交错写入**直接 400 报错**。**必须物理隔离**。

### 2.2 session 的角色

session 这个概念**同时服务多个目的**：

| 目的 | 含义 |
|------|------|
| 隔离独立工作流 | 不同任务不互相污染 |
| 防并发串扰 | 写 race、读错序、context 干扰 |
| 限定 resource scope | 工具、数据、配置生效到哪儿 |
| artifact 归属 | 跑出来的东西归这次 run |

**之前我们把它想窄了**——以为只是"切话题降 context"。实际上 session 是**"独立工作流的容器"**，context 隔离只是它一个应用。

### 2.3 检索不能替代 session

哪怕检索 100% 准确，也救不了"两个 session 交错"的问题：

- **协议硬约束**：`tool_use_id` ↔ `tool_result` 必须配对，交错就 400
- **推理线程断**：agent 推理是线性的，**插话就断**
- **文件层 race**：两个进程并发写同一文件

**记忆层 = 检索擅长**。**活儿层 = session 提供**。两者不替代。

---

## 3. 最终方案

### 3.1 核心原则

> **每次 agent 启动 = 一个新 session。要接续显式 `--continue`。**

理由：
- **多 agent 并行自然不冲突**——两个进程 = 两个 session = 两个目录
- **不需要锁**——一个 session 一个进程，从来不并发
- **不需要 mainsession 概念**——所有 session 平级
- **不需要 auto-fork**——默认开新 session 本身就在 fork

### 3.2 跟 Claude Code 对齐

这个设计正是 Claude Code 的做法：

```
# Claude Code 默认
claude                   ← 全新 session
claude --continue        ← 接续最近
claude --resume <id>     ← 接续指定
claude --session <name>  ← 显式命名
```

---

## 4. 目录结构

```
~/.codeagent/
├── .migrated_from_cwd
└── projects/
    └── <sanitized-cwd>/                  ← sanitize 后用 - 替 /
        ├── .migrated_to_persession
        ├── <uuid-1>/                     ← 第一次跑（无 flag）
        │   ├── session.json
        │   └── session.sql
        ├── <uuid-2>/                     ← 第二次跑
        │   ├── session.json
        │   └── session.sql
        ├── eval-2026-07-13/              ← --session eval-2026-07-13
        │   ├── session.json
        │   └── session.sql
        └── ...
```

**没有 `mainsession/`**——它是"最新一次跑的 session"的隐喻，不是物理实体。`--continue` 找的是**当前 cwd 下 mtime 最新的 session 目录**。

---

## 5. CLI 形状

```bash
# 默认：每次启动 = 新 session
python -m agent "fix bug"
# 行为：生成新 UUID，开新 session 目录

# 接续最近一次
python -m agent --continue "继续"
# 行为：找当前 cwd mtime 最新的 session，从它的 messages[] 接着跑

# 接续指定 session
python -m agent --resume <id-or-name> "..."

# 显式命名（eval、批处理）
python -m agent --session eval-2026-07-13 "..."
# 行为：用这个确切的名字。撞名直接报错。
```

**flag 矩阵**：

| flag | 行为 |
|------|------|
| 无 | 新 UUID session |
| `--continue` | 找最新 session 接续 |
| `--continue <id>` | 接续指定 id |
| `--session <name>` | 用确切名字，撞名报错 |

---

## 6. 已决定的点

### 6.1 变量 rename

| 旧 | 新 |
|---|---|
| `MEMORY_DIR`  | `SESSION_DIR`  |
| `MEMORY_FILE` | `SESSION_FILE` |
| `MEMORY_SQL`  | `SESSION_SQL`  |

**理由**：本次设计意图是"session"，"memory"这个词跟事实抽取层绑得太紧，用在 session 文件上容易混。

### 6.2 session 名

- **无 flag** → 生成 UUID（永不相撞）
- **`--session <name>`** → 用户写，**撞名报错**
- **`--continue`** → 不命名，找最新

### 6.3 跨 session 可见性

**每个 session 只看见自己的历史**。**默认不跨 session**。**跨 session 检索是未来事**（Claude Code 的 `memory/*.md` 模式），**这次不碰**。

### 6.4 不引入新文件

这次**只动位置和命名**。不引入 `events.jsonl`、`meta.json`、`memory/` 等结构。**这些是后续迭代**。

### 6.5 不需要锁

之前讨论的 fcntl/flock + auto-fork 整条思路**作废**。新设计下：

- **一个 session 一个进程**——不可能并发写
- **session 间不同目录**——不可能撞
- **锁无意义**

### 6.6 不需要 mainsession

`mainsession/` **不存在**。它是"最新 session"的**逻辑概念**（`--continue` 的搜索目标），不是**物理实体**。

---

## 7. 暂不做的事

明确**这次范围之外**，避免 scope creep：

- 不做跨 session 检索
- 不做 facts 抽取 / memory 层
- 不做云同步
- 不做 session 元数据（created_at、tokens、title 等）
- 不做 sub-agent session 隔离（sub-agent 复用同样的 `--continue`/`--session` 机制）
- 不做 per-session contexts 配置
- 不做文件锁
- 不做 auto-fork

---

## 8. 迁移

旧 `~/.codeagent/session.{json,sql}`（单文件） → `projects/<sanitized-cwd>/<session-uuid>/session.{json,sql}`。

**一次性自动迁移**：
- 启动时检测旧位置
- 给个 UUID 当新 session 名
- 把内容搬到 `projects/<cwd>/<uuid>/session.{json,sql}`
- 写 `.migrated_to_persession` 标志
- 幂等
- **跟现有的 `.migrated_from_cwd` 独立**，不冲突

**`--continue` 第一次跑能找回这次内容**——mtime 最新。

---

## 9. JSON / JSONL 的取舍

**新设计下并发问题不存在**，但 **JSON array 的"读-改-写"全量重写**仍然是个**O(N) 性能**问题。

**当前决定**：**保持 JSON array**，**不切 JSONL**。理由：
- 性能问题**还没撞上**——session 文件还不算大
- 切 JSONL 是**独立重构**（动 `_append_session` 全部逻辑、迁移格式、改名）
- 切不切是**性能优化**问题，不是**并发安全**问题

**触发切 JSONL 的时机**：单 session 文件 > 10MB 或 append 明显卡顿时。

---

## 10. 决策日志

- **2026-07-13**：提出 session 隔离需求（eval 不能污染主）
- **2026-07-13**：讨论"session 是手工分块工具"——过窄
- **2026-07-13**：用户提出 session 是"独立工作流容器"，多目的（context + 并发 + scope + artifact）
- **2026-07-13**：考虑过 mainsession + auto-fork + 单写者锁方案
- **2026-07-13**：用户重新分析，决定**每次启动 = 新 session + --continue**
- **2026-07-14**：方案定型，写入本文档
