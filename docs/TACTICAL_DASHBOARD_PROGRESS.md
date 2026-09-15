# TACTICAL_DASHBOARD_PROGRESS

> RMUC Tactical Intelligence 平台的持续进度记录。每完成一个可独立描述的阶段性进展，
> 更新本文件并 `commit + push`。

---

## 最近一次验证结果

- **M2（Frontend 框架）验证（2026-09-15）**：
  - `cd web && npm run build` → **通过**（tsc -b 无错误；Vite 产出 dist，gzip 约 400 kB）。
  - 生产模式端到端：FastAPI 托管 `web/dist`，浏览器打开 `http://127.0.0.1:8000` → 深色三栏
    布局、Layers 面板、时间轴、底部 tabs 全部渲染；`/api/teams` 98 队；选择「广东工业大学」
    → 历史比赛 20 场即时加载、对手画像进入计算（首算约 32 s，M4 缓存优化）、战术地图渲染
    红蓝点位与 HP 环。
- **M1（Backend 基础）验证**：`pytest tests` → **15 passed**；真实库冒烟全通过
  （health 613 场 / teams / profile / match / state / events / timeline）。
- **M0 验证**：仓库审计完成，架构文档落地。

---

## 已完成

- [x] **M0 仓库审计** — 结构/SQLite schema/RL 推理/viz 全通读；`docs/TACTICAL_DASHBOARD.md` + 本文件。
- [x] **M1 Backend 基础**
  - `rm_rl/tactical/`：schemas、team_identity（alias + 签名缓存）、conditions、analytics
    （条件占位热力图）、flow、formations、events、meta（视频偏移 + 多锚点分段对齐）、opponent。
  - `rm_rl/api/`：FastAPI 应用工厂（CORS、健康检查、静态托管 web/dist）+ 全部路由。
  - `tests/`：合成数据库 fixture，15 个后端测试全绿。
- [x] **M2 Frontend 框架**
  - `web/`：Vite + React 18 + TypeScript + Zustand + ECharts + PixiJS（依赖就绪，PixiJS M3 启用）。
  - 深色视觉系统 `src/theme.ts` + `src/styles.css`（F1 telemetry × 军事态势图风格；
    红 `#ff5b3d` / 蓝 `#4d9dff` / AI 青 `#3fc9c9` / 危险橙 `#ff8f4d`；统一 transition 200–350 ms）。
  - 全局状态 `src/state/store.ts`：`useTimeline`（global tactical time / 播放 / 倍速 0.5–4x）、
    `useSelection`（队伍/比赛）、`useConditions`（阶段/结构/人数筛选）、`useLayers`（13 个图层开关）。
  - API client `src/api/client.ts`：typed fetch 封装，覆盖 teams/matches/state/timeline/heatmap/
    flow/formation/event-response/videos（含锚点与双向时间映射）。
  - 组件：Header、FilterBar（对手/比赛/兵种/阶段/结构/人数）、Timeline（播放/暂停/±10s/0.5–4x/
    拖动/事件标记轨道）、OpponentPanel（雷达摘要 + 9 指标对比表 + 历史比赛列表）、
    TacticalMap（SVG 场地图初版：28×15 m、红蓝阵营、HP 环、朝向、建筑区、Layers 面板、raw t 标注）、
    ConclusionsPanel（事件→行为概率条，带 n/n_matches）、TabsPanel（条件统计/阵型/对手比较/
    AI分析/历史证据五 tab，阵型 ECharts 时序初版）、RadarChart。
  - 构建：`web/dist` 已生成并被 FastAPI 生产模式托管；`web/node_modules` gitignore。

## 当前状态

- 可运行：
  - 后端：`python -m rm_rl.api.app` → http://127.0.0.1:8000（生产模式自动托管 web/dist）。
  - 前端开发：`cd web && npm run dev` → http://localhost:5173（/api 代理到 8000）。
- 下一步：**M3 动态战术地图**（PixiJS 平滑插值渲染、最近 N 秒轨迹、HP、事件动画、时间轴同步）。

## 如何运行（随里程碑更新）

```bash
# 数据准备（一次）
# 1. 官方数据集解压到 dataset/rmuc_2026_region_dataset.sqlite（已就绪，gitignore 不提交）
# 2. 先验（RL 推理需要，M8 前准备）
#    python -m rm_rl.data.vis_map --db dataset/rmuc_2026_region_dataset.sqlite --out data/vis_map.npz
#    python -m rm_rl.data.team_prior --db dataset/rmuc_2026_region_dataset.sqlite --out data/team_prior.json

# 生产模式（一条命令）
conda activate rl_tactical
python -m rm_rl.api.app                 # http://127.0.0.1:8000 直接打开平台

# 前端开发模式
cd web && npm install && npm run dev    # http://localhost:5173

# 测试
python -m pytest tests -q               # 15 passed（后端）
cd web && npm run build                 # 前端构建验证
```

## 已知问题

- `/api/teams/{id}/profile` 首算较慢（联盟平均抽样 30 队，约 30 s）；M4/M6 用预计算缓存解决。
- 全联盟 heatmap/flow 未加 limit 时逐场扫描（613 场），M4 引入 cache。
- 刷新页面后前端选择状态重置（M2 未做 URL/持久化），后续里程碑补充。
- B 站 iframe 双向控制受跨域限制：以平台时间轴为主时间轴，iframe 定位为单向 seek（M7 落实）。

## 数据假设

- `timeseries.时刻秒` 1 Hz 整数秒（0 起）；`x=y=0` 丢失跟踪；建筑/工程 yaw 恒 `-140.0` 哨兵值。
- `events.目标robot_id` 对发弹/受击为 NULL → 目标归因用几何推断（软标签）。
- 蓝方统计统一镜像到红方坐标系（canonical）；地图展示用原始帧。
- 视频关联属"视频关联演示"层：数据库无逐秒数据时不伪造 game_id/时间同步。
- 开火门控由累计 17mm 发弹差分读出；"发弹"行为检测同理。

## 下一阶段

- M3：PixiJS 动态战术地图（机器人/平滑插值/轨迹/HP/事件动画/时间轴同步）。
- M4：heatmap / conditional heatmap / flow field / engagement / layer manager + 预计算缓存。
- M5：阵型分析时间序列图（后端已有，前端补全）。
- M6：Opponent Intelligence 页面（画像、联盟对比、事件响应、状态转移、matchup）。
- M7：Bilibili 集成（iframe、锚点标定 UI、证据片段）。
- M8：RL 推理集成（IQL/BC/DT、policy overlay、人机分歧）。
- M9：相似局面检索。M10：战术卡与自动总结。

## Git 记录

- 远程：`git@github.com:kswlt/rl-vison.git`（origin/main 跟踪）。
- M0 提交：`6d5ad83` docs: tactical dashboard architecture baseline。
- M1 提交：`09a8e6c` feat(api): add FastAPI backend with team/match/timeline/analytics/video endpoints and tests。
- M2 提交：见下一条（本阶段提交后更新 SHA）。
