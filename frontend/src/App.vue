<template>
  <router-view />
</template>

<style>
/* ============ 全局主题 ============ */
:root {
  /* 主色: 博物馆深蓝 */
  --hz-primary: #1d3f72;
  --hz-primary-light: #2b5aa0;
  --hz-primary-lighter: #eef3fa;
  /* 语义色 */
  --hz-success: #22a05a;
  --hz-warning: #e6a23c;
  --hz-danger: #e05252;
  --hz-info: #8a94a6;
  /* 中性色 */
  --hz-text: #2c3345;
  --hz-text-secondary: #6b7280;
  --hz-border: #e6eaf0;
  --hz-bg: #f3f5f9;
  --hz-card-radius: 12px;
  --hz-shadow: 0 2px 12px rgba(29, 63, 114, 0.08);
}

* { margin: 0; padding: 0; box-sizing: border-box; }
html, body, #app { height: 100%; }
body {
  font-family: 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', sans-serif;
  color: var(--hz-text);
  -webkit-font-smoothing: antialiased;
}

/* ============ Element Plus 全局微调 ============ */
.el-card {
  border: none;
  border-radius: var(--hz-card-radius);
  box-shadow: var(--hz-shadow) !important;
}
.el-card__header {
  font-weight: 600;
  border-bottom: 1px solid var(--hz-border);
}
.el-button { font-weight: 500; }
.el-button--primary {
  --el-button-bg-color: var(--hz-primary);
  --el-button-border-color: var(--hz-primary);
  --el-button-hover-bg-color: var(--hz-primary-light);
  --el-button-hover-border-color: var(--hz-primary-light);
}
.el-table {
  --el-table-header-bg-color: #f7f9fc;
  --el-table-header-text-color: var(--hz-text-secondary);
  --el-table-border-color: var(--hz-border);
}
.el-table th.el-table__cell { font-weight: 600; }
.el-dialog { border-radius: var(--hz-card-radius); }
.el-dialog__title { font-weight: 600; }
.el-pagination { justify-content: flex-end; }
.el-tag { border-radius: 6px; }

/* 页面通用容器: 每个路由视图包一层留白 */
.page-view { padding: 4px 2px; }
.page-view > .el-card { margin-bottom: 16px; }

/* 列表页工具栏统一 */
.toolbar {
  display: flex; gap: 12px; margin-bottom: 16px; flex-wrap: wrap; align-items: center;
}
.toolbar .spacer { flex: 1; }
.toolbar-title { font-size: 15px; font-weight: 700; color: var(--hz-text); }
</style>
