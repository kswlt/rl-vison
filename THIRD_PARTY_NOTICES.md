# Third-Party Notices / 第三方材料声明

本仓库的 [MIT License](LICENSE) **仅覆盖本项目自身的代码与文档**。以下材料不在
其范围内,各自权利归原权利人所有。

## RMUC 2026 区域赛数据集

比赛数据由大疆创新(DJI)/ RoboMaster 组委会官方发布,版权归其所有。本仓库
**不包含、不分发**任何比赛数据,请自行从官方渠道获取(见 [README](README.md)
「获取数据」一节)。

由此派生的产物同样不予分发:`viz/replays/*.json` 是单场比赛逐秒裁判系统状态的
机器可读再编码,等同于数据集切片,已在 `.gitignore` 中排除。仓库内保留的
`viz/figures/*.png` 为聚合统计图表,属衍生分析结果。

## 场地俯视图

`viz/assets/rmuc_2026_field_top_view.jpeg` 出自 RMUC 2026 规则手册,版权归
大疆创新(DJI)所有,**不随本仓库分发**,需使用者自行放置,详见
[viz/assets/README.md](viz/assets/README.md)。

仓库内 `viz/figures/*.png` 中,部分图表以该场地图为底图(经压暗、去饱和处理),
就此范围而言同样不在本仓库 MIT 协议覆盖之内。用
`--no-field-image` 重新生成即可得到不含该素材的版本。

## 场地标定参数

回放器与绘图脚本使用的场地裁切标定(源图 1683 × 938 px,有效场地内框
(100, 69, 1576, 856) px)取自开源项目
[ezthor/rm-battlescope](https://github.com/ezthor/rm-battlescope)
(MIT License),该项目同样基于本届官方数据集。

## Bilibili 比赛视频

战术情报平台(web/ + rm_rl/api/)仅**保存视频的元数据**——原始 URL、BVID、
标题与人工标定的时间对齐锚点(`data/tactical_meta.sqlite` 中的 `match_videos`
与 `video_alignment_points`),并在页面中以官方 `player.bilibili.com`
iframe 嵌入播放。本仓库**不下载、不重新分发**任何视频内容;视频版权归
原上传者/平台所有。视频库中的种子条目(全国赛第五十三场
上海交通大学 vs 广东工业大学,BV18Tup6uEg5)仅作关联演示,不与
2026 区域赛逐秒数据伪造绑定。

## 前端依赖

`web/` 使用 React、TypeScript、Vite、PixiJS、ECharts 等开源库,各自遵循其
MIT / Apache-2.0 等开源许可,详见各依赖包内 LICENSE。

## 商标

RoboMaster、RMUC 及相关名称与标识为大疆创新(DJI)的商标。本项目为独立的
第三方研究工作,**未获得 DJI 或 RoboMaster 组委会的授权、认可或背书**。
