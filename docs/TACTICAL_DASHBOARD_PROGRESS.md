# TACTICAL_DASHBOARD_PROGRESS

> RMUC Tactical Intelligence 平台的持续进度记录。每完成一个可独立描述的阶段性进展，
> 更新本文件并 `commit + push`。

---

## 最近一次验证结果

- **2026-09-15**：完成 Milestone 0 仓库审计。git 工作区干净，仓库 `main` 分支与
  `origin/main` 同步（`ee7c717`）。SQLite 数据库（613 matches / 4,015,383 timeseries /
  1,474,178 events）schema 核实无误；`rm_rl` 核心（schema/features/build_dataset/
  vis_map/team_prior/deploy）与 `viz` 工具通读完毕；文档 `docs/TACTICAL_DASHBOARD.md`
  落地。
- 环境：专用 conda 环境 `rl_tactical`（Python 3.11）待建（网络安装依赖中）。

---

## 已完成

- [x] **M0 仓库审计**
  - 项目结构 / SQLite schema / RL 推理接口 / viz 工具 / 数据来源全部通读。
  - 写出 `docs/TACTICAL_DASHBOARD.md`（架构基线）与本进度文件。
  - 确认数据事实：1 Hz 采样、28×15 m 场地、robot_id 布局、事件类型、队伍先验与
    交火图先验、161 维观测构建路径。

## 当前状态

- 环境搭建：创建 `rl_tactical` conda 环境并安装依赖（torch CPU / pandas / numpy /
  fastapi / uvicorn / pydantic / pyyaml / tqdm）。
- 下一步：Milestone 1 — Backend 基础（FastAPI 应用骨架 + team/match/timeline API +
  Pydantic schemas + 后端测试），完成后 commit + push。

## 如何运行（随里程碑更新）

```bash
# 数据准备（一次）
# 1. 从官方论坛下载 RMUC 2026 数据集解压到 dataset/rmuc_2026_region_dataset.sqlite
# 2. （可选，先验）python -m rm_rl.data.vis_map --db dataset/rmuc_2026_region_dataset.sqlite --out data/vis_map.npz
#    python -m rm_rl.data.team_prior --db dataset/rmuc_2026_region_dataset.sqlite --out data/team_prior.json

# 后端（M1 后可用）
conda activate rl_tactical
python -m rm_rl.api.app                 # http://localhost:8000/docs

# 前端（M2 后可用）
cd web && npm install && npm run dev
```

## 已知问题

- 暂无（Milestone 0 审计阶段）。

## 数据假设

- `timeseries.时刻秒` 为 1 Hz 整数秒（0 起）；`x=y=0` 为丢失跟踪；建筑/工程机 yaw 恒为
  `-140.0` 哨兵值。
- `events.目标robot_id` 对发弹/受击为 NULL → 目标归因一律用几何推断（枪口朝向与敌方
  方位夹角，softmax 软标签）。
- 蓝方分析统一镜像到红方坐标系（仅统计口径；地图展示用原始帧）。
- 视频关联属"视频关联演示"层：数据库无对应逐秒数据时不伪造 game_id 或时间同步。

## 下一阶段

- M1：FastAPI 骨架、teams/matches/timeline API、analytics 基础 schemas、后端测试。
- M2：React + TypeScript 前端框架与深色视觉系统。
- M3：PixiJS 动态战术地图。
- 后续：M4–M10 按架构文档推进，每个里程碑完成后更新本文件并 push。

## Git 记录

- `main` 分支；远程 `origin https://github.com/kswlt/RMUC-OfflineRL.git`。
- 本阶段提交：待 M0 提交（docs + 环境脚本）后记录 SHA。
