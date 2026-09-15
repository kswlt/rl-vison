# TACTICAL_DASHBOARD_PROGRESS

> RMUC Tactical Intelligence 平台的持续进度记录。每完成一个可独立描述的阶段性进展，
> 更新本文件并 `commit + push`。

---

## 最近一次验证结果

- **M7（Bilibili 视频集成）验证（2026-09-15）**：
  - 视频库：`python -m rm_rl.tactical.seed_videos` 幂等写入全国赛第五十三场
    （上海交通大学 交龙战队 VS 广东工业大学 DynamicX战队，BV18Tup6uEg5），
    note 明示"全国赛不在 2026 区域赛数据集，仅作视频库演示"——不伪造 game_id。
  - 浏览器端到端：历史证据 tab → 视频库条目 → [预览] → 官方 iframe
    `player.bilibili.com/player.html?bvid=BV18Tup6uEg5&t=0&danmaku=0&autoplay=0&high_quality=1`
    加载成功（弹幕默认关、不自动播放）；[在B站打开] 链接可用；console 0 错误。
  - 时间同步链路（API 验证，临时关联后清理）：offset=222 + 多锚点
    (0→222, 180→405, 360→591) → game 0/90/180/270/360 s ⇒ video
    222/313.5/405/498/591 s；反向 video 313.5 s ⇒ game 90 s，分段线性精确。
  - 比赛页 VideoPanel（播放器 + ●已校准/○未校准 + 暂停时 [设为比赛开始]/[新增锚点]
    标定 UI + 平台时间→B站时间单向驱动）构建通过；窄屏（<1180px）按设计隐藏。
  - `npm run build` 通过；`pytest tests` → **17 passed**（新增视频库关联测试）。
- **M6（对手情报 + 对阵分析）验证（2026-09-15）**：
  - `GET /api/analytics/matchup?team_a=上海交通大学&team_b=广东工业大学`：3 场共同比赛、
    3 次首次交火（平均 24.7 s）、争夺区 121 格、双方位置热力 304/164 格；响应带
    `note="历史统计，非未来预测"`；首算 473 ms，走磁盘缓存。
  - 浏览器端到端：对手比较 tab → 我方广工 / 对方上海交大 → 分析对阵 →
    地图「历史典型路线」层自动开启并渲染三色 overlay（蓝=A 队 635px、红=B 队 18.8kpx、
    橙=争夺区 9.8kpx）+ 黄色首次交火圆点 + overlay 标签；迷你热图 + 首次交火时间分布柱状图；
    React 错误 0、console 错误 0。
  - **修复**：事件回调中调用 zustand hook（`useLayers().setLayer`）导致 React #321
    （minified "hooks" 错误）→ 改用 `useLayers.getState().setLayer`。
  - `npm run build` 通过；`pytest tests` → **16 passed**（新增 matchup 测试）。
- **M5（阵型分析）验证（2026-09-15）**：
  - 地图实时阵型：播放中每帧计算红蓝双方 centroid / 横向宽度 / 纵向纵深 / 平均间距 /
    连接多边形 / 边界框，红蓝两色低饱和半透明绘制（地图区域检出红 109 + 蓝 525 像素），
    控制台 0 错误。
  - 阵型时序图补全：宽度/纵深/平均间距/集中程度四序列 ECharts（后端 formations 数据）。
- **M4（多维空间分析 + 缓存）验证**：磁盘缓存 profile 32.2s→3ms、heatmap 170ms→3ms；
  地图叠加层（条件热力图 + 运动流场）渲染，图层开关/条件联动，控制台 0 错误。
- **M3（动态战术地图）验证**：states 批量端点 419s 首算 390ms；播放插值动画 + 事件动画正常。
- **M2 / M1 / M0 验证**：`npm run build` 通过；`pytest tests` 15 passed；架构文档落地。

---

## 已完成

- [x] **M0 仓库审计** — 结构/SQLite schema/RL 推理/viz 全通读；`docs/TACTICAL_DASHBOARD.md` + 本文件。
- [x] **M1 Backend 基础**
  - `rm_rl/tactical/`：schemas、team_identity（alias + 签名缓存）、conditions、analytics
    （条件占位热力图）、flow、formations、events、meta（视频偏移 + 多锚点分段对齐）、opponent。
  - `rm_rl/api/`：FastAPI 应用工厂（CORS、健康检查、静态托管 web/dist）+ 全部路由。
  - `tests/`：合成数据库 fixture，15 个后端测试全绿。
- [x] **M2 Frontend 框架** — Vite + React 18 + TS + Zustand + ECharts；深色视觉系统
  （theme.ts / styles.css，F1 telemetry × 军事态势图）；全局状态（useTimeline 全局战术时间、
  useSelection、useConditions、useLayers 13 图层）；typed API client；Header / FilterBar /
  Timeline（播放/暂停/±10s/0.5–4x/拖动/事件标记）/ OpponentPanel（雷达摘要 + 指标表 + 比赛列表）/
  ConclusionsPanel（事件响应概率条）/ TabsPanel（五 tab，阵型 ECharts 时序）；`web/dist` 提交，
  FastAPI 生产托管。
- [x] **M3 动态战术地图**
  - 后端：`GET /api/matches/{id}/states?step=` 批量逐秒状态（整场 419 s 首算 390 ms）。
  - 前端 `web/src/components/map/pixiMap.ts`：PixiJS 渲染器——场地网格/半场着色/基地警戒区；
    机器人平滑插值（1 Hz 数据 → 60 FPS 显示，明确区分 raw second 与 interpolated frame）；
    红蓝 HP 环、朝向线、阵亡灰化、丢失跟踪淡化；最近 10 s 轨迹（默认）与完整轨迹（上限 120 s）；
    受击 pulse / 阵亡 flash 事件动画；图层开关实时映射到 Pixi 容器。
  - `TacticalMap.tsx` 重写：整场 states + events 预加载、全局战术时间驱动、13 图层面板保留。
  - 窄屏降级：< 1180 px 隐藏左右栏、地图占满（保持"场地是视觉中心"）。

- [x] **M4 多维空间分析 + 缓存**
  - 后端 `rm_rl/tactical/cache.py`：磁盘 JSON 战术缓存（键 = kind + 条件组合 + DB 签名；
    换库自动失效），profile / conditional heatmap / flow 全部走缓存；
    `AppState.cached()` / `State.cached()` 统一入口；`invalidate_all` / `cache_stats` 工具。
  - 前端 Pixi overlay：`setHeatmap` / `setFlow` 渲染条件热力图（单色低饱和 alpha 渐变、
    标注 n / n_matches / 样本不足）与运动流场（箭头方向=平均运动、长度=速度、透明度=样本密度）；
    图层开关与条件筛选实时联动；fire/hit/engage/routes 图层诚实占位（不伪造数据）。

- [x] **M5 阵型分析**
  - 地图实时阵型层：播放中逐帧计算红蓝双方 centroid/宽度/纵深/平均间距、连接多边形与
    边界框（红蓝低饱和半透明），随机器人连续移动。
  - 阵型时序 tab 补全：宽度/纵深/平均间距/集中程度四序列（ECharts）。

- [x] **M6 对手情报 + 对阵分析**
  - 后端 `rm_rl/tactical/matchup.py`：双队历史对阵——共同比赛、双方典型位置热力、
    几何首次交火检测（3 m 内、按秒取最早）、争夺区（双方占用同格）、首次交火时间分布；
    响应显式标注"历史统计，非未来预测"；`GET /api/analytics/matchup` 走缓存。
  - 前端：对手比较 tab（A/B 队伍选择 → 迷你位置热图 + 首次交火柱状图 + 样本行）；
    Pixi 地图「历史典型路线」层渲染三色 overlay（蓝 A / 红 B / 橙争夺区 / 黄首次交火点），
    分析时自动开启该图层；事件响应案例点击 → 跳转对应比赛 + 时间（地图/时间轴联动）。
  - 修复事件回调误调 zustand hook（React #321）→ `.getState()`。

- [x] **M7 Bilibili 视频集成**
  - 后端：`video_library` 表（无 game_id 的未关联视频，全国赛第五十三场 BV18Tup6uEg5
    经 `python -m rm_rl.tactical.seed_videos` 幂等入库）；`GET/POST /api/videos/library`、
    `POST /api/videos/library/{id}/associate`（只允许真实存在的 game_id）；
    offset + 多锚点分段对齐双向映射（已有，API 验证）。
  - 前端：`BiliPlayer`（官方 iframe，danmaku=0/autoplay=0，失败 fallback「在B站打开」；
    seek 通过重建 iframe 的 t 参数，平台时间轴为主）；`VideoPanel`（比赛页录像面板：
    多视频切换、●已校准/○未校准、暂停时 [设为比赛开始]/[新增锚点] 标定、平台时间→B站时间
    单向驱动）；历史证据 tab 视频库（预览 + 关联到比赛，全国赛明确标注为视频库演示）。

## 当前状态

- 可运行：
  - 后端：`python -m rm_rl.api.app` → http://127.0.0.1:8000（生产模式自动托管 web/dist）。
  - 前端开发：`cd web && npm run dev` → http://localhost:5173（/api 代理到 8000）。
- 下一步：**M8 Offline RL 集成**（IQL/BC/DT 推理、policy overlay、人机分歧；
  需先运行 `python -m rm_rl.data.vis_map` / `team_prior` 生成先验并训练/放置模型）。

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

- M4：heatmap / conditional heatmap / flow field / engagement / layer manager + 预计算缓存。
- M5：阵型分析时间序列图（后端已有，前端补全 + 地图实时阵型多边形）。
- M6：Opponent Intelligence 页面（画像、联盟对比、事件响应、状态转移、matchup）。
- M7：Bilibili 集成（iframe、锚点标定 UI、证据片段）。
- M8：RL 推理集成（IQL/BC/DT、policy overlay、人机分歧）。
- M9：相似局面检索。M10：战术卡与自动总结。

## Git 记录

- 远程：`git@github.com:kswlt/rl-vison.git`（origin/main 跟踪）。
- M0 提交：`6d5ad83` docs: tactical dashboard architecture baseline。
- M1 提交：`09a8e6c` feat(api): add FastAPI backend with team/match/timeline/analytics/video endpoints and tests。
- M2 提交：`6a15e52` + `5ecfd99` feat(web): initialize React/TS tactical dashboard。
- M3 提交：`54529b4` feat(map): add animated PixiJS tactical battlefield…。
- M4 提交：`1b31641` feat(analytics): add disk tactical cache… + heatmap/flow overlays。
- M5 提交：`5b1fc3d` feat(analytics): draw live formation polygons… + formation time-series。
- M6 提交：`d8e38b5` feat(opponent): add matchup analysis… with map overlay and event-case drill-down。
- M7 提交：见下一条（本阶段提交后更新 SHA）。
