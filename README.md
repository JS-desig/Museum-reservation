# 菏泽市科技博物馆预约与门禁系统

集"线上预约、后台管理、闸机核销、数据看板"于一体的综合预约与门禁系统全栈实现。

## 技术栈

| 端 | 技术 |
|---|---|
| 后端API | Python 3.11 + FastAPI + SQLAlchemy + MySQL 5.7 |
| B端后台 | Vue 3 + Element Plus + ECharts + Vite |
| C端小程序 | 微信小程序原生框架(页面代码+API对接) |
| 测试体系 | Pytest + Requests + Allure + Faker + SQL对账 |
| CI | GitHub Actions + 本地 run_ci.sh |

## 目录结构

```
HeZe/
├── sql/schema.sql              # 数据库建表脚本(14张表)
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI入口(路由统一/api前缀)
│   │   ├── core/               # 配置/安全(JWT+AES+bcrypt)/响应/依赖
│   │   ├── models/models.py    # ORM模型
│   │   └── routers/            # auth认证 content内容 reservation预约
│   │                           # gate闸机核销 stats统计 admin_manage权限
│   ├── seed.py                 # 种子数据
│   └── tests/                  # 接口自动化测试(98条) + 冒烟/对账脚本
├── frontend/                   # B端管理后台 + 闸机终端页面
├── miniapp/                    # C端小程序页面代码(6页面4件套完整)
├── docs/测试用例设计文档.md        # 252条用例设计(含闸机异常专项)
├── docs/上线前冒烟检查清单.md      # 11项核心链路发布门禁(需求7.3)
├── .github/workflows/ci.yml    # CI流水线(测试+对账+构建)
├── run_ci.sh                   # 本地CI一键脚本
└── 菏泽市科技博物馆预约与门禁系统需求文档.md
```

## 快速启动

### 1. 数据库

MySQL 5.7 服务运行中(mysql57), 密码按 `DB_PASSWORD` 环境变量, 默认 `1234`:

```bash
mysql -uroot -p1234 < sql/schema.sql
cd backend && python seed.py
```

### 2. 后端(端口8000)

```bash
cd backend
pip install -r requirements.txt
python seed.py                     # 首次运行写种子数据
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

API文档: http://127.0.0.1:8000/docs

### 3. B端后台(端口5173)

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173

| 账号 | 密码 | 角色 |
|---|---|---|
| admin | admin123 | 系统管理员(全部权限) |
| operator | operator123 | 场馆管理员(无账号管理) |

页面: 数据看板 / 预约管理 / 核销记录 / 公告 / 展品 / 场馆配置 / 时段容量 / 黑名单 / 账号权限 / **闸机终端**

### 4. 闸机终端

后台右上角"闸机终端"标签或直接访问 http://localhost:5173/gate

- 扫码核销(输入/生成12位预约码) + 身份证核销
- 绿屏开闸/红屏拒绝/语音提示语模拟
- **离线模式**: 开关切换, 断网指令本地暂存, 恢复后批量补传(幂等去重, 按实际过闸时间落库)

### 5. C端小程序

`miniapp/` 为微信开发者工具工程(填入 appid 即可运行), API对接见 `miniapp/utils/api.js`, 基地址指向后端8000端口。页面: 首页(场馆信息/公告/选日期时段) → 预约填单(实名+同行人) → 预约码 → 我的(预约记录/通行记录)。

## 测试体系

```bash
cd backend
python -m pytest tests/ -v              # 98条接口自动化用例, Allure结果输出到 allure-results/
allure serve allure-results             # 查看Allure报告(需allure命令行)

python tests/fake_data.py --users 50 --with-passes   # Faker批量造数(预约+70%核销率)
python tests/fake_data.py --users 20 --date 2026-10-10

python tests/sql_consistency.py         # SQL数据一致性对账(7项硬校验, 退出码0/1)
python tests/smoke_test.py              # 上线前冒烟: 11项核心链路(退出码0=可发布)
```

### 性能基线(tests/test_08_perf.py)

需求六性能指标纳入自动化断言, 取多次采样最坏值避免抖动误报:

- 闸机核销 < 0.5s / 预约创建 < 1s / 时段查询 < 1s / 看板聚合 < 1s

### 上线前冒烟检查(需求7.3)

`tests/smoke_test.py` 覆盖 11 项核心链路, 见 `docs/上线前冒烟检查清单.md`:

预约链路: 健康检查 → 场馆 → 公告 → 展品 → 登录实名 → 选时段 → 预约
核销链路: 核销入馆(绿屏开闸) → 重复核销拦截(红屏) → 出馆 → 数据对账

任一项失败退出码 1 并阻断发布; 服务不可达时 2 秒内预检中止。

### 闸机异常场景覆盖(tests/test_03_gate.py)

- **重复核销**: 同device_seq幂等返回首次结果 / 不同seq业务拦截(60002)
- **断网重连**: 离线批量补传, 单条失败不影响其余 / 补传幂等去重
- **指令延迟**: 补传按实际过闸时间pass_time落库, 预约核销时间与通行日志一致
- **错峰**: 非预约日期核销拒绝(60004); 无效码(60001); 未预约(60003); 黑名单(60005)
- **性能**: 闸机核销响应 < 0.5s 断言

### 并发/竞态压测(tests/test_10_concurrency.py)

- **名额不超卖**: 容量5/20并发、容量6/10并发(每单2人) => 精确用满且不超卖
- **同序号并发幂等**: 同device_seq并发8次 => 仅1次实际核销, 不产生500
- **选人竞态**: 单人并发不同序号仅放行1次; 多人并发各核销一次不重复计数

## 核心设计

### 数据一致性(需求五)

- 预约扣减名额、同行人明细、限次计数**同事务提交**
- 核销成功 => `check_record` + `access_log` + 预约状态更新**同事务**
- 出馆与入馆对称记录, 实时在馆人数 = 通行日志 in - out(对账基准)
- 手动核销同样补通行日志, 保证统计口径
- `sql_consistency.py` 7项硬校验: 已核销必有日志、成功核销↔日志一一对应、无重复入馆、取消后无入馆等

### 防刷机制

- 同证件同日预约次数上限(默认3次, 可配 `MAX_RESV_PER_CARD_PER_DAY`)
- 同证件同日同时段唯一约束
- 单笔最多5人实名同行
- 身份证校验位验证 + 防重放nonce
- 黑名单拦截(预约与核销双侧)

### 安全

- 实名信息 AES-GCM 加密(Base64存储), 仅保留脱敏展示字段(`1101**********8670`)
- 密码 bcrypt 哈希; 后台 JWT 鉴权 + 角色控制
- 闸机核销以 `(gate_id, device_seq)` 唯一约束实现指令幂等

### 性能(需求六)

- 核销接口纯索引查询+单事务写入, 测试断言 < 0.5s
- 统计口径聚合查询走 `(visit_date, session_id, status)` 组合索引
