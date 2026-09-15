# RMUC Tactical Intelligence — 架构文档

> 本文档是 `RMUC Tactical Intelligence`（下称"战术情报平台"）的架构与设计基线。
> 定位：RMUC 比赛**动态战术情报、对手研究、AI 辅助决策与录像复盘**平台，面向战队教练、
> 操作手、哨兵算法组与战术组。它不是 ML 调试器。
>
> 配套进度文档：[TACTICAL_DASHBOARD_PROGRESS.md](TACTICAL_DASHBOARD_PROGRESS.md)

---

## 1. 仓库审计结论（Milestone 0 基线）

### 1.1 数据层

官方数据集为单个 SQLite 文件（`dataset/rmuc_2026_region_dataset.sqlite`，1.18 GB），三张表：

| 表 | 行数 | 关键字段（中文原名，代码内映射为 ASCII 别名） |
|---|---|---|
| `matches` | 613 | 赛区 / 场次号 / 赛程 / 局号 / game_id / web_game_id / 红方学校 / 蓝方学校 / 胜方 / 开始时间 / 时长秒 |
| `timeseries` | 4,015,383 | game_id / 时刻秒(1Hz) / robot_id / 机器人类型 / 阵营 / 学校名 / 对手学校 / 当前血量 / 最大血量 / x / y / z / 枪口朝向 / 底盘功率 / 小热量(上限) / 大热量(上限) / 累计17mm发弹 / 累计42mm发弹 / 队伍总金币 / 队伍剩余金币 / 是否易伤 |
| `events` | 1,474,178 | game_id / 时刻秒 / 事件类型(发弹/受击/装配成功/能量机关/飞镖闸门开/飞镖命中/雷达反制UAV/增益) / robot_id / 机器人类型 / 阵营 / 学校名 / 目标robot_id / 目标类型 / 类别 / 数值 / 备注 |

关键数据事实（由审计与 README 确认）：

- 采样率 **1 Hz**，单局约 420 s；`robot_id` 红方：1 英雄 / 2 工程 / 3 步兵3 / 4 步兵4 / 6 空中 / 7 哨兵 / 10 基地 / 11 前哨站；蓝方 +100。
- 场地 **28 m × 15 m**；`x=y=0` 表示裁判系统丢失跟踪；建筑与工程机 `枪口朝向` 恒为哨兵值 `-140.0`（无云台数据）。
- `events.目标robot_id` 对发弹/受击均为 NULL → **无法逐机器人伤害归因**，只能做队伍级与几何推断级分析。
- 无视线/障碍物信息 → 可见性由 `rm_rl/data/vis_map.py` 的经验交火图代理。
- 累计发弹是**累计值**，某段时间发弹数 = 末秒累计 − 首秒累计。
- 96 支队伍，每队中位 12 场；`matches.开始时间` 为文本时间戳（因果排序用）。

### 1.2 现有 RL 核心（必须复用、不得破坏）

- `rm_rl/data/schema.py` — 中文列名 → ASCII 别名映射、场地常量、robot_id 布局、事件类型常量。**新代码一律经 schema 取列名，禁止散落硬编码中文列名。**
- `rm_rl/data/features.py` — 161 维观测 + tactical 动作构建：
  - `build_obs(game, camp, agent_type, ...)` → `[T, 161]`，蓝方自动 180° 镜像到红方坐标系；
  - `build_action_raw(...)` → 人类动作（tactical 10 维：nav 2 + fire 1 + soft-target 7）；
  - `target_soft` / `fire_gate`：目标软标签与开火门控。
- `rm_rl/data/build_dataset.py` — `load_game_arrays(con, gid)`（逐秒时间对齐、ffill、越界裁剪）、`load_matches(con)`。
- `rm_rl/data/vis_map.py` — 2 m 栅格（14×8=112 格）经验交火先验 `VisibilityMap`。
- `rm_rl/data/team_prior.py` — 严格因果、匿名的队伍强度先验 `TeamPrior`（winrate/aggression/durability）。
- `rm_rl/deploy.py` — `load_policy(run_dir)`（IQL/BC/DT 统一加载，优先 best.pt）、`decode_action`（含蓝方反镜像）、`MLPPolicyRunner.step(obs161)`、`apply_safety`。**这是 RL 推理的唯一入口。**
- `configs/` — infantry_{iql,bc,dt}_tactical.yaml 为主配置（hidden 256×2，tactical 动作空间）。

### 1.3 现有 viz（保留为 legacy/debug 工具）

`viz/` 四件套：`export_replay.py`（比赛+模型决策 → JSON）、`replay.html`（Canvas 回放）、`heatmaps.py`（占位证据图）、`policy_field.py`（策略向量场）、`field_canvas.py`（场地底图标定）、`serve.py`（本地静态服务）。全部直接读官方数据集与训练策略。**新平台不删除它们**；新平台与 viz 的职责边界：

- viz = 单场决策回放 / 统计证据图 / 策略诊断（legacy）。
- Tactical Intelligence = 跨场战术统计、对手画像、条件分析、录像证据、AI 分歧复盘（new）。

### 1.4 环境

- 仓库要求 Python 3.10+ / torch 2.1+。本机系统 Python 3.14 无依赖；专用 conda 环境 `rl_tactical`（Python 3.11）承载新平台与现有训练/推理。
- 依赖：torch、numpy、pandas、pyyaml、tqdm + FastAPI/uvicorn/pydantic。

### 1.5 数据安全与版权

- 官方数据切片（replay JSON、逐秒导出）一律不提交 GitHub（`.gitignore` 已覆盖 `/viz/replays/`、`*.sqlite`、`*.npz` 等）。
- 场地俯视图为 DJI 素材，不随仓库分发。
- B 站视频只保存 URL/BVID/时间锚点/元数据，不下载不重分发。
- `THIRD_PARTY_NOTICES.md` 已存在，随新增能力补充。

---

## 2. 总体架构

```
SQLite / RMUC Dataset
   ├── matches / timeseries / events / team metadata
   └── RL inference (load_policy + build_obs + decode_action)
                │
                ▼
      Python Tactical Analytics Layer          rm_rl/tactical/
   （聚合统计、条件筛选、阵型、流场、事件响应、相似检索、视频对齐）
                │
                ▼
              FastAPI                          rm_rl/api/
   Pydantic schemas · 参数校验 · 错误返回 · 预计算缓存
                │
                ▼
        React + TypeScript                     web/
   ┌────────────┬──────────────┬─────────────┐
   │   PixiJS   │   ECharts    │  Bilibili   │
   │ Tactical   │   Charts     │    Video    │
   │    Map     │              │   iframe    │
   └────────────┴──────────────┴─────────────┘
```

### 2.1 设计原则

1. **SQLite 是事实来源**；预计算缓存（`data/tactical_cache.sqlite` + NPZ/JSON）只加速查询，禁止复制一套互相不一致的数据。缓存带 schema/数据版本号，版本不符自动重建。
2. **队名归一化**：数据库学校名、视频标题别名（如 广东工业大学 / DynamicX / 广工）统一由后端 `team identity` 层解析，前端不做字符串硬匹配。
3. **统计可靠性**：所有战术统计携带样本量（n、涉及比赛数）；n 低于阈值时 UI 显示"样本不足"，禁止制造虚假确定性。
4. **数据真实性**：正式模式无数据即显示"暂无数据 / 样本不足 / 未关联录像 / 未加载模型"；开发模式 mock 必须标注 DEMO DATA。
5. **性能**：613 场 / 400 万行不逐次全扫。按 (team, robot, role, event, condition, time_phase) 预计算并建索引；常规筛选目标 < 300 ms。
6. **RL 集成**：推理必须经 `build_obs` 完整构造观测（合成 ego 位置时友军相对位、敌方距离方位、vis prior 全部同步更新），不得只改两列。

### 2.2 目录结构（新增部分）

```
RMUC-OfflineRL/
├── rm_rl/
│   ├── tactical/                  # 新增：战术分析层
│   │   ├── __init__.py
│   │   ├── schemas.py             # Pydantic 请求/响应模型
│   │   ├── team_identity.py       # 队名归一化 / alias
│   │   ├── conditions.py          # 条件筛选定义（阶段/结构/人数/机器人状态）
│   │   ├── analytics.py           # 条件热力图 / 占位统计
│   │   ├── flow.py                # 运动流场
│   │   ├── formations.py          # 阵型指标
│   │   ├── events.py              # 事件触发行为分析
│   │   ├── opponent.py            # 对手画像
│   │   ├── matchup.py             # 双队对抗比较
│   │   ├── similarity.py          # 相似历史局面检索
│   │   ├── video_alignment.py     # 视频锚点 / 分段对齐
│   │   ├── summarizer.py          # 规则式战术总结 / 战术卡
│   │   ├── cache.py               # 预计算缓存管理
│   │   └── inference.py           # RL 推理服务（复用 deploy.py + features.py）
│   └── api/
│       ├── __init__.py
│       ├── app.py                 # FastAPI 应用工厂
│       └── routes/
│           ├── __init__.py
│           ├── teams.py
│           ├── matches.py
│           ├── analytics.py
│           ├── videos.py
│           ├── inference.py
│           └── similar.py
├── web/                           # 新增：React + TS + Vite + PixiJS + ECharts
├── scripts/
│   ├── precompute_cache.py        # 预计算缓存构建
│   └── run_tactical_dashboard.py  # 一键启动
├── docs/
│   ├── TACTICAL_DASHBOARD.md      # 本文档
│   └── TACTICAL_DASHBOARD_PROGRESS.md
└── viz/                           # 原样保留（legacy）
```

### 2.3 数据模型（tactical 侧）

- **比赛维度**：`match`（613 局，含 red/blue school、winner、region、duration、开始时间）。
- **机器人维度**：每局每阵营 8 类实体；`robot_id` 唯一；`type` ∈ {英雄, 工程, 步兵3, 步兵4, 空中, 哨兵, 基地, 前哨站}。
- **事件维度**：8 类事件，按 (game_id, t) 对齐。
- **视频维度**（新表，存于 `data/tactical_meta.sqlite`）：
  - `match_videos(id, game_id, platform, bvid, url, title, offset, alignment_status, created_at)`
  - `video_alignment_points(id, match_video_id, game_time, video_time, confidence)`
  - 基础模式 `game_time = video_time - offset`；多锚点分段对齐（piecewise）。
- **队伍身份**（新表）：`team_identity(team_id, school_name, team_name, aliases[])`，含内置别名表（广东工业大学 → DynamicX 等）。

### 2.4 API 约定

- 前缀 `/api`；所有响应 JSON；参数经 Pydantic 校验；错误统一 `{"detail": ...}`。
- 核心端点（实际命名以 routes 实现为准）：
  - `GET /api/teams`、`GET /api/teams/{id}`、`GET /api/teams/{id}/profile`、`GET /api/teams/{id}/matches`
  - `GET /api/matches/{id}`、`GET /api/matches/{id}/timeline`、`GET /api/matches/{id}/state?t=`、`GET /api/matches/{id}/events`
  - `GET /api/analytics/heatmap`、`GET /api/analytics/flow`、`GET /api/analytics/formation`、`GET /api/analytics/event-response`、`GET /api/analytics/matchup`、`GET /api/analytics/brief`
  - `GET /api/similar-states`、`POST /api/inference`
  - `GET /api/videos/{game_id}`、`POST /api/videos`、`POST /api/videos/{id}/anchors`
- 统一时间轴：`global tactical time`（秒，距开局 0 起），所有组件共用。

### 2.5 前端架构

- React 18 + TypeScript + Vite；状态用简单 React/Zustand；视觉中心为 **PixiJS 动态战术地图**；统计图表用 ECharts。
- 视觉基调：F1 Telemetry + 电竞数据 + 军事态势图（深灰/炭黑底、低饱和场地、红蓝语义、青色 AI 推荐、橙红危险区、统一动效 200–600 ms）。
- 核心视图：动态战术地图（机器人/轨迹/HP/事件/阵型/热区/流场/RL 建议，图层开关）、统一时间轴（播放/暂停/倍速/±10s/拖动）、对手画像、条件热力图、事件响应、状态转移、对抗比较、人机分歧、相似局面、赛前战术卡。
- 1 Hz 原始数据在前端做平滑插值（raw timestamp vs interpolated display state 明确区分），不伪造更高频真实数据。

---

## 3. 分析能力设计（要点）

### 3.1 条件热力图
- 条件维度：队伍 / 兵种 / 比赛阶段（0–30s、30–120s、中期、最后120/90/60s、自定义）/ 结构状态（前哨各血量档、基地受击）/ 人数状态 / 机器人状态（低/高血量、高/低弹量）。
- 输出：1 m（或可配置）栅格占位密度 + 样本数 + 涉及比赛数 + 置信度提示；条件切换 400–600 ms 过渡。

### 3.2 运动流场
- 网格聚合运动向量：箭头方向 = 平均移动方向、长度 = 平均速度、透明度 = 样本数；点击网格显示样本数 / 平均进入方向 / 平均离开方向 / 平均停留时间 / 常见下一位置。

### 3.3 阵型分析
- 单帧指标：centroid、横向宽度、纵向纵深、平均间距、最前/最后机器人、阵型方向、面积、集中程度；地图实时绘制 + 时间序列图表（进攻展开 → 回防 → 收缩）。

### 3.4 事件触发行为分析
- 事件 X（前哨掉血档、前哨摧毁、基地受击、某兵种阵亡/残血、人数优劣势、最后 N 秒）发生后未来 N 秒的行为分布（回防/保持/前压等，按规则分类）。
- 输出：行为 + 概率 + n + 比赛数 + 证据案例列表（game_id, t, 对手, 视频锚点）。点击行为 → 地图只显示真实案例。

### 3.5 对手画像
- 指标：攻击性、前场占位率、回防速度、阵型稳定性、侧翼利用率、固定位置依赖、主动交战率、前哨保护倾向、残局收缩倾向；目标队 vs 联盟平均 vs Top 队伍平均；Radar 只作摘要，核心比较用实际数字表。

### 3.6 人机分歧
- 扫描整场，综合 target/nav-cos/fire 分歧，输出 Top N 分歧局面；措辞为"AI 与真人明显分歧，值得复盘"，不宣称 AI 更正确。

### 3.7 相似局面检索
- 不直接对 161 维等权欧氏距离；设计带权重的 state similarity（比赛剩余时间、结构血量、存活、HP、队伍相对位置、阵型、空间位置、弹量），支持可配置权重；返回 Top-K 相似历史局面与后续轨迹。

### 3.8 战术总结（规则式）
- 确定性规则 + 真实统计生成"人能看懂"的总结（开局/前哨受压/残局），全部附样本数与比赛数；不做"必胜策略"。
- `Tactical Brief`：一页赛前战术卡（对手特点、关键规律、建议区域、典型路线、事件响应、真实证据），打印友好。

---

## 4. 实施里程碑（与 PROGRESS 文档联动）

| 里程碑 | 内容 | 产出 |
|---|---|---|
| M0 | 仓库审计 | 本文档 + PROGRESS |
| M1 | Backend 基础 | FastAPI + teams/matches/timeline + schemas + tests |
| M2 | Frontend 框架 | React+TS 主布局、深色视觉、Team/Match 选择、时间轴、API client |
| M3 | 动态战术地图 | PixiJS 场地图、机器人、平滑移动、轨迹、HP、事件动画、时间轴同步 |
| M4 | 多维空间分析 | heatmap / conditional heatmap / flow field / engagement / layer manager |
| M5 | 阵型分析 | centroid/width/depth/spacing/concentration + 时间序列图 |
| M6 | Opponent Intelligence | 单队画像、联盟对比、事件响应、状态转移、matchup |
| M7 | Bilibili 集成 | BVID 存储、iframe、锚点对齐、证据片段、手工标定 UI |
| M8 | RL 集成 | IQL/BC/DT 推理、policy overlay、人机分歧检测 |
| M9 | 相似局面 | similarity metric、top-K、历史轨迹、录像集成 |
| M10 | 战术总结 | Tactical Brief、自动战术文字、样本量、证据链接、一页会议模式 |

每个里程碑完成即 `commit + push`，并更新 PROGRESS 文档。
