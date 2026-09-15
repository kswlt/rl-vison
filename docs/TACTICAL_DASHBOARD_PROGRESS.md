# TACTICAL_DASHBOARD_PROGRESS

> RMUC Tactical Intelligence 平台的持续进度记录。每完成一个可独立描述的阶段性进展，
> 更新本文件并 `commit + push`。

---

## 最近一次验证结果

- **M1（Backend 基础）验证（2026-09-15）**：
  - `pytest tests` → **15 passed**（team normalization / timeline / conditional filters /
    formation / event response / video offset / piecewise alignment / API surface）。
  - 真实库冒烟：`/api/health` 613 场；`/api/teams` 96 队；`DynamicX` alias → 广东工业大学
    （20 场）；`/api/teams/DynamicX/profile` 9 项画像指标（首算 32 s，含联盟平均抽样，
    后续里程碑用预计算缓存优化）；match/state/events/timeline 端点全部 200。
- **M0 验证**：仓库审计完成，架构文档落地，`main` 已推至远程 `kswlt/rl-vison`。

---

## 已完成

- [x] **M0 仓库审计** — 结构/SQLite schema/RL 推理/viz 全通读；`docs/TACTICAL_DASHBOARD.md` + 本文件。
- [x] **M1 Backend 基础**
  - `rm_rl/tactical/`：schemas（Pydantic 契约）、team_identity（alias 归一化 + 签名缓存）、
    conditions（阶段/结构/人数/机器人状态条件）、analytics（条件占位热力图 + TacticalStore）、
    flow（运动流场）、formations（阵型指标）、events（事件触发行为分析）、meta（视频关联表 +
    偏移 + 多锚点分段对齐）、opponent（9 项画像指标 vs 联盟平均）。
  - `rm_rl/api/`：FastAPI 应用工厂（CORS、健康检查、静态托管 web/dist）、routes
    （teams / matches / analytics / videos / inference）。
  - 端点：`/api/teams[/{id}|/{id}/profile|/{id}/matches]`、
    `/api/matches[/{id}|/{id}/timeline|/{id}/state|/{id}/events]`、
    `/api/analytics/heatmap|flow|formation|event-response`、
    `/api/videos/{game_id}`、`POST /api/videos`、`POST /api/videos/{id}/anchors`、`/api/videos/{id}/map|inverse`。
  - `tests/`：合成数据库 fixture（不依赖 1.18 GB 真实数据），15 个后端测试全绿。
  - 环境：conda `rl_tactical`（Python 3.11，torch 2.14 CPU + fastapi/uvicorn/pydantic/pandas/numpy）。

## 当前状态

- M1 已可运行：`python -m rm_rl.api.app` → http://127.0.0.1:8000/docs。
- 下一步：**M2 Frontend 框架**（React + TypeScript + Vite，深色视觉系统，Team/Match 选择、
  统一时间轴、API client），完成后 commit + push。

## 如何运行（随里程碑更新）

```bash
# 数据准备（一次）
# 1. 官方数据集解压到 dataset/rmuc_2026_region_dataset.sqlite（已就绪，gitignore 不提交）
# 2. 先验（RL 推理需要，先放着）
#    python -m rm_rl.data.vis_map --db dataset/rmuc_2026_region_dataset.sqlite --out data/vis_map.npz
#    python -m rm_rl.data.team_prior --db dataset/rmuc_2026_region_dataset.sqlite --out data/team_prior.json

# 后端
conda activate rl_tactical
python -m rm_rl.api.app                 # http://127.0.0.1:8000/docs

# 测试
python -m pytest tests -q               # 15 passed

# 前端（M2 后可用）
cd web && npm install && npm run dev
```

## 已知问题

- `/api/teams/{id}/profile` 首算较慢（联盟平均抽样 30 队，约 30 s）；M4/M6 用预计算缓存解决。
- 全联盟 heatmap/flow 未加 limit 时逐场扫描（613 场），M4 引入 cache。
- B 站 iframe 双向控制受跨域限制：以平台时间轴为主时间轴，iframe 定位为单向 seek（M7 落实）。

## 数据假设

- `timeseries.时刻秒` 1 Hz 整数秒（0 起）；`x=y=0` 丢失跟踪；建筑/工程 yaw 恒 `-140.0` 哨兵值。
- `events.目标robot_id` 对发弹/受击为 NULL → 目标归因用几何推断（软标签）。
- 蓝方统计统一镜像到红方坐标系（canonical）；地图展示用原始帧。
- 视频关联属"视频关联演示"层：数据库无逐秒数据时不伪造 game_id/时间同步。
- 开火门控由累计 17mm 发弹差分读出；"发弹"行为检测同理。

## 下一阶段

- M2：React + TS 前端框架、深色视觉系统、Team/Match 选择、统一时间轴、API client。
- M3：PixiJS 动态战术地图（机器人/平滑插值/轨迹/HP/事件动画/时间轴同步）。
- M4：heatmap / conditional heatmap / flow field / engagement / layer manager + 预计算缓存。
- M5：阵型分析时间序列图。
- M6：Opponent Intelligence 页面（画像、联盟对比、事件响应、状态转移、matchup）。
- M7：Bilibili 集成（iframe、锚点标定 UI、证据片段）。
- M8：RL 推理集成（IQL/BC/DT、policy overlay、人机分歧）。
- M9：相似局面检索。M10：战术卡与自动总结。

## Git 记录

- 远程：`git@github.com:kswlt/rl-vison.git`（origin/main 跟踪）。
- M0 提交：`6d5ad83` docs: tactical dashboard architecture baseline。
- M1 提交：见下一条（本阶段提交后更新 SHA）。
