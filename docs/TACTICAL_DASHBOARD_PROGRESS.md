# TACTICAL_DASHBOARD_PROGRESS

> RMUC Tactical Intelligence 平台的持续进度记录。每完成一个可独立描述的阶段性进展，
> 更新本文件并 `commit + push`。

---

## 最近一次验证结果

- **M10 完成（2026-09-15）——赛前战术卡 + 规则式自动战术总结**：
  - 新增 `rm_rl/tactical/brief.py`：**确定性规则式总结器（不依赖在线 LLM）**，全部复用
    平台已有真实统计——开局经 `flow_field(phase=open30)` 算左右半场活动占比、
    前哨受压经 `event_response(kinds=[outpost_lt50])` 取 15s 内回防/保持/前压分布、
    残局经 opponent profile 的 endgame_shrink/position_fix vs 联盟平均。
  - 每条结论必带 `n`（样本数）+ `n_matches`（比赛数）+ 真实案例列表（≤6 条，
    含 opponent/时间/行为），n<5 自动标"样本不足"；note 明示"历史统计，非未来预测"。
  - 新 schema：`BriefPoint/BriefSection/TacticalBriefOut`（清理两处旧版重复定义）；
    新 API：`GET /api/analytics/tactical-brief?team=<school|alias>`（Pydantic 校验，
    alias 解析，未知队 404）。
  - **广工真实数据验证（20 场）**：开局 0-30s 右半场活动 67%（n=3595）→
    建议优先控制中左、避免无准备正面争右；前哨 HP<50% 后 15s 保持 56%/回防 16%/前压 14%
    （n=112，20 场）→ 行为较分散、注意多线拉扯（附 6 个真实案例按钮，点击跳转对应比赛+时刻）；
    残局收缩程度 0.33 vs 联盟平均 -7.21 → 增加横向拉扯避免进入重叠火力区。
  - 前端：新增「赛前战术卡」tab（`BriefTab`）——生成按钮/自动加载、三栏结论卡片、
    证据 case 列表（点击 `selectGame + seek` 联动地图与时间轴）、[打印/导出] 按钮 +
    `@media print` 一页打印布局。
  - 修复：behaviors 值本身已是百分比（原先重复 ×100 导致 1610%）、`_rate` 传 tuple
    （`100*top` → `top[1]`）、BehaviorCase 字段名（`behavior` → `detail`）。
  - `npm run build` 通过；`pytest tests` → **27 passed**（新增 M10 3 项：brief 端点结构 +
    样本量字段、未知队 404、alias 解析）。浏览器端到端（生产 build）：选广工 →
    赛前战术卡 tab → 开局/前哨受压/残局三段 + 证据案例按钮 + 打印按钮，console 0 错误。
  - 补 `THIRD_PARTY_NOTICES.md`：Bilibili 仅存元数据（URL/BVID/锚点）不下载不分发声明。
  - M10 提交 SHA 见下方 Git 历史。
- **M8 完成 + M9 完成（2026-09-15）**：
  - **真实 BC 模型训练**：`build_dataset --limit-games 150`（train 220,698 步 / val 24,570 步，
    obs 161 / act 10）→ `train_offline --config configs/infantry_bc_tactical.yaml
    --max-steps 6000`（CPU，step 3000 best action_mse=0.0669，fire_acc 0.83，
    target_top1_named 0.40）→ `rm_runs/infantry_bc_tactical/best.pt`（1.3 MB，gitignore 不入库）。
  - **真实推理链路（非 mock）**：`POST /api/inference`（bc）返回 200——完整 161-D obs
    （load_game_arrays → build_obs，含 vis_map/team_prior 先验）+ `MLPPolicyRunner.step` +
    `build_action_raw` 真人对比 + 分歧分。验证样例：BC 建议 移动(-1.40,-2.07) 目标无/开火否，
    真人 移动(-0.94,3.66)，分歧 1.663；`POST /api/inference/disagreements` 整场 419 s 扫描
    0.3 s（游戏缓存生效）→ Top-K。iql/dt 无权重仍 501 诚实。
  - **浏览器端到端（生产 build）**：AI 分析 tab → BC 分析当前局面 → 建议卡片
    （移动 4.8m/-0.5m、目标 哨兵 27%、开火 不建议、人机分歧 1.089）+ 地图青色 RL 建议箭头
    overlay（起点=真实机器人坐标）+ 真人实际动作对比；分歧扫描 Top 20（4.6 s）；
    相似局面 Top 20（比赛/时间/相似度/后续行为/未来轨迹，点击跳转对应比赛+时间）；
    console 错误 0。
  - **M9 相似局面**：`rm_rl/tactical/similarity.py` 20-D 特征（剩余时间/结构 HP/存活/阵型
    centroid+宽深/ego 位置 HP yaw/敌队相对），加权 L2；全 613 场特征表预计算 44.9 s 走磁盘
    缓存（100,348 行），查询 ~1 s；`GET /api/analytics/similar-states` 返回候选数 +
    Top-K + 后续行为 + 未来轨迹，note 明示"相似≠预测"。
  - `npm run build` 通过；`pytest tests` → **24 passed**（新增 M8 5 项 + M9 2 项）。
  - **遗留说明**：IQL / Decision Transformer 无现成权重（训练管线完整，跑
    `train_offline --config configs/infantry_iql_tactical.yaml` / `infantry_dt_tactical.yaml`
    即可）；vis_map 当前为 100 场子集版（71% pair-coverage），全量重跑命令见下。
- **M8a（推理管线+AI tab）验证（2026-09-15）**：见上；`POST /api/inference` 无权重 501 诚实、
  先验生成（team_prior 96 队 / vis_map 112 cells）、150 场训练集构建完成。
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

- [x] **M8 Offline RL 集成（完成）**
  - 后端 `rm_rl/tactical/rl.py`：`TacticalRL` 懒加载 vis_map/team_prior/policy；
    完整 161-D obs 构造（复用 `build_obs`，禁止只改 ego x/y）、真人动作读取、人机分歧评分
    （nav 余弦 + fire XOR + target argmax，[0,~3]）；游戏数据 LRU 缓存。
  - `POST /api/inference`（真实 BC 权重推理）+ `POST /api/inference/disagreements`
    （整场逐秒扫描 Top-K）；iql/dt 无权重 501 诚实，不伪造推理。
  - 前端 AI 分析 tab：BC/IQL/DT 选择、当前局面推理建议卡片（移动/目标/开火/分歧）、
    青色 RL 建议箭头 overlay（起点=真实 ego 坐标）、真人实际动作对比、全场分歧 Top 20
    点击跳转。
  - 真实训练：150 场子集 BC 模型（`rm_runs/infantry_bc_tactical/best.pt`，gitignore）。
- [x] **M9 历史相似局面检索（完成）**
  - `rm_rl/tactical/similarity.py`：20-D curated 特征（时间/结构/存活/阵型/自身/敌队相对），
    可配权重加权 L2；全 613 场特征表磁盘缓存（100,348 行）；查询排除本场、返回 Top-K +
    真人后续行为 + 未来 10/20 s 轨迹 + "相似≠预测" 声明。
  - `GET /api/analytics/similar-states` + 前端 AI tab「查找相似历史局面」列表点击跳转。
- [x] **M10 赛前战术卡 + 自动战术总结（完成）**
  - `rm_rl/tactical/brief.py` 规则式总结器（无在线 LLM）：开局（flow open30 左右占比）、
    前哨受压（event_response outpost_lt50 15s 行为分布）、残局（profile vs 联盟平均）。
  - `GET /api/analytics/tactical-brief?team=`（alias 解析；Pydantic 校验；未知队 404；
    每条结论带 n/n_matches/insufficient/真实案例列表）。
  - 前端「赛前战术卡」tab：生成入口、结论卡片、证据案例按钮（点击跳比赛+时刻）、
    [打印/导出] + `@media print` 一页打印布局。
  - 补 `THIRD_PARTY_NOTICES.md`（B站仅存元数据声明）。

## 当前状态

- 可运行：
  - 后端：`python -m rm_rl.api.app` → http://127.0.0.1:8000（生产模式自动托管 web/dist）。
  - 前端开发：`cd web && npm run dev` → http://localhost:5173（/api 代理到 8000）。
  - AI 分析：bc 权重就绪即可用；iql/dt 需先训练。
- **M0–M10 全部完成**。剩余可选增强：IQL/DT 真权重训练、全量 vis_map、相似度查询索引优化、
  更细粒度条件组合的战术卡段落。
- `pytest tests` → 27 passed；`npm run build` 通过。

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
python -m pytest tests -q               # 22 passed（后端）
cd web && npm run build                 # 前端构建验证

# RL 推理（M8）
# 先验（已生成，data/ 不入库）：
#   python -m rm_rl.data.team_prior --db dataset/rmuc_2026_region_dataset.sqlite --out data/team_prior.json
#   python -m rm_rl.data.vis_map --db dataset/rmuc_2026_region_dataset.sqlite --out data/vis_map.npz
# 训练数据 + 模型：
#   python -m rm_rl.data.build_dataset --db dataset/rmuc_2026_region_dataset.sqlite \
#     --out data/infantry_tactical --agent infantry --action-mode tactical --goal-horizon 5 \
#     --config configs/infantry_bc_tactical.yaml --vis-map data/vis_map.npz --team-prior data/team_prior.json
#   python -m rm_rl.train.train_offline --config configs/infantry_bc_tactical.yaml
#   权重落到 rm_runs/infantry_bc_tactical/{best.pt|final.pt}；env 可覆盖 RMUC_BC_DIR/RMUC_IQL_DIR/RMUC_DT_DIR
```

## 已知问题

- `/api/teams/{id}/profile` 首算较慢（联盟平均抽样 30 队，约 30 s）；M4/M6 用预计算缓存解决。
- 全联盟 heatmap/flow 未加 limit 时逐场扫描（613 场），M4 引入 cache。
- 刷新页面后前端选择状态重置（M2 未做 URL/持久化），后续里程碑补充。
- B 站 iframe 双向控制受跨域限制：以平台时间轴为主时间轴，iframe 定位为单向 seek（M7 落实）。
- **RL 推理当前依赖训练好的权重**：`rm_runs/infantry_bc_tactical` 已就绪；iql/dt
  需要运行对应 config 训练后才可用（无权重时 501 诚实"模型未加载"，前端同样提示）。
- **vis_map 当前为 100 场子集版（pair-coverage 71%）**：全量 613 场版需去掉
  `--limit-games` 重跑（耗时较长）；后续可直接覆盖 data/vis_map.npz。

## 数据假设

- `timeseries.时刻秒` 1 Hz 整数秒（0 起）；`x=y=0` 丢失跟踪；建筑/工程 yaw 恒 `-140.0` 哨兵值。
- `events.目标robot_id` 对发弹/受击为 NULL → 目标归因用几何推断（软标签）。
- 蓝方统计统一镜像到红方坐标系（canonical）；地图展示用原始帧。
- 视频关联属"视频关联演示"层：数据库无逐秒数据时不伪造 game_id/时间同步。
- 开火门控由累计 17mm 发弹差分读出；"发弹"行为检测同理。

## 下一阶段

- M0–M10 全部完成并已推送。可选增强（非阻塞）：
  - 训练 IQL/DT 真权重（`train_offline --config configs/infantry_iql_tactical.yaml` /
    `infantry_dt_tactical.yaml`）使 AI tab 三种模型可切换；
  - 全量 vis_map（去掉 `--limit-games` 重跑，替换 100 场子集版）；
  - 战术卡增加更多条件组合段落（人数优/劣势、阵亡触发、能量机关）；
  - 相似度查询加 ANN 索引；选择状态 URL 持久化。

## Git 记录

- 远程：`git@github.com:kswlt/rl-vison.git`（origin/main 跟踪）。
- M0 提交：`6d5ad83` docs: tactical dashboard architecture baseline。
- M1 提交：`09a8e6c` feat(api): add FastAPI backend with team/match/timeline/analytics/video endpoints and tests。
- M2 提交：`6a15e52` + `5ecfd99` feat(web): initialize React/TS tactical dashboard。
- M3 提交：`54529b4` feat(map): add animated PixiJS tactical battlefield…。
- M4 提交：`1b31641` feat(analytics): add disk tactical cache… + heatmap/flow overlays。
- M5 提交：`5b1fc3d` feat(analytics): draw live formation polygons… + formation time-series。
- M6 提交：`d8e38b5` feat(opponent): add matchup analysis… with map overlay and event-case drill-down。
- M7 提交：`3108444` feat(video): add bilibili match video integration…（视频库 + 关联 + 标定 UI）。
- M8a 提交：`5bcec77` feat(ai): add tactical RL inference API and AI analysis tab…（+ `9a56d20` tsbuildinfo）。
- M8/M9 提交：`712d34a` feat(ai,similarity): train real BC checkpoint, wire full-obs inference +
  disagreement scan, and add similar-state retrieval with cached 613-game feature table。
- M10 提交：本阶段完成后更新 SHA（feat(brief): add rule-based tactical brief + one-page brief tab）。
