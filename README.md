# HallSpan 考场间距排座

在考室网格上按最小曼哈顿距离排座，同试卷套不得四邻相邻，并输出违规与统计。

技术栈：Python 3.12 / FastAPI / SQLAlchemy / PostgreSQL / Vue 3 / TypeScript / Vite

## 启动

```bash
docker compose up --build
```

| 服务 | 地址 |
| --- | --- |
| 前端 | http://localhost:4900 |
| API | http://localhost:9900 |
| API 文档 | http://localhost:9900/docs |
| Postgres | localhost:5450 |

健康检查：`GET http://localhost:9900/api/health`

## 使用说明

1. 在「考室」「考生」「试卷套」确认基础数据。
2. 打开「排座图」执行间距排座。
3. 在「违规」查看间距或同卷相邻问题。
4. 在「统计」查看占用与违规汇总。

## 前排名额台账

- 考室的「前排行数」> 0 时开启名额账：前 N 行为特殊考生名额格，名额格数在每次排座提交时按 行数×列数 重算并写入台账（`GET /api/seating/ledger`），不沿用上次缓存。
- 特殊考生（「考生」页可标记）只消耗名额格并优先落座；普通考生不占用名额格。名额不够时整场排座失败（409），不增方案、不留半本台账。
- 排座图、名额已耗、统计前排占用同一套数，对不齐即整场失败回滚。
- 前排行数为 0 关闭名额账、退回原排座行为；行数为负或大于考室行数时拒绝保存（422），台账/方案/统计保持原状。
- 历史方案钉死生成当时的名额数字，改行数或改标记不回刷，下一次排座提交才重算。

## 开发与测试

```bash
docker compose exec api pytest -q
```
