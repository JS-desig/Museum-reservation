#!/usr/bin/env bash
# 本地CI模拟: 一键跑完 接口测试 + SQL对账 + 前端构建
set -e
cd "$(dirname "$0")"

echo "===== 1/4 后端接口自动化测试 ====="
cd backend
python -m pytest tests/ -v --tb=short --alluredir=allure-results --clean-alluredir

echo "===== 2/4 SQL数据一致性对账 ====="
python tests/sql_consistency.py

echo "===== 3/4 上线前冒烟检查(11项核心链路) ====="
python tests/smoke_test.py

echo "===== 4/4 前端构建 ====="
cd ../frontend
npm run build

echo ""
echo "✅ CI全部通过"
