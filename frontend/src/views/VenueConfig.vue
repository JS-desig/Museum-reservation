<template>
  <el-row :gutter="16">
    <!-- 左列: 基础信息 -->
    <el-col :xs="24" :md="12">
      <el-card class="full-card">
        <template #header>
          <div class="card-head"><span class="card-head-bar"></span>基础信息</div>
        </template>
        <el-form label-width="110px" v-loading="loading">
          <el-form-item label="场馆名称"><el-input v-model="form.name" /></el-form-item>
          <el-form-item label="地址"><el-input v-model="form.address" /></el-form-item>
          <el-form-item label="开闭馆时间"><el-input v-model="form.open_time" /></el-form-item>
          <el-form-item label="每日最大承载">
            <el-input-number v-model="form.max_daily" :min="100" :step="500" />
            <span class="field-hint">节假日按此上限控制预约总量</span>
          </el-form-item>
          <el-form-item label="开放状态">
            <el-switch v-model="form.status" :active-value="1" :inactive-value="0"
                       active-text="开放" inactive-text="闭馆" />
            <span class="field-hint">闭馆后 C 端停止预约</span>
          </el-form-item>
        </el-form>
      </el-card>
    </el-col>

    <!-- 右列: 指引与须知 -->
    <el-col :xs="24" :md="12">
      <el-card class="full-card">
        <template #header>
          <div class="card-head"><span class="card-head-bar"></span>指引与须知</div>
        </template>
        <el-form label-width="110px">
          <el-form-item label="交通指引">
            <el-input v-model="form.traffic_guide" type="textarea" :rows="4"
                      placeholder="公交 / 自驾 / 停车信息, 每行一条" />
          </el-form-item>
          <el-form-item label="入馆须知">
            <el-input v-model="form.notice" type="textarea" :rows="7"
                      placeholder="入馆须知内容, 将展示在小程序首页" />
          </el-form-item>
        </el-form>
      </el-card>
    </el-col>
  </el-row>

  <!-- 保存操作条 -->
  <el-card class="save-bar">
    <div class="save-row">
      <span class="save-hint">修改后立即生效, 全部操作将记录审计日志</span>
      <el-button type="primary" @click="save">保存配置</el-button>
    </div>
  </el-card>
</template>

<script setup>
import { reactive, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

const form = reactive({})
const loading = ref(true)

onMounted(async () => {
  const { data } = await http.get('/venue')
  Object.assign(form, data)
  loading.value = false
})

async function save() {
  await http.put('/admin/venue', form)
  ElMessage.success('已保存')
}
</script>

<style scoped>
.full-card { height: 100%; }
.card-head { display: flex; align-items: center; gap: 8px; }
.card-head-bar {
  width: 4px; height: 16px;
  border-radius: 2px;
  background: var(--hz-primary);
}
.field-hint { color: #9aa3b2; font-size: 12px; margin-left: 12px; }
.save-bar { margin-top: 16px; }
.save-row { display: flex; justify-content: flex-end; align-items: center; gap: 16px; }
.save-hint { color: #9aa3b2; font-size: 13px; }
</style>
