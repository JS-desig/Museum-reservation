import axios from 'axios'
import { ElMessage } from 'element-plus'
import router from '../router'

const http = axios.create({ baseURL: '/api', timeout: 10000 })

http.interceptors.request.use(cfg => {
  const token = localStorage.getItem('token')
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

http.interceptors.response.use(
  resp => {
    const body = resp.data
    if (body && typeof body.code === 'number' && body.code !== 0) {
      if (body.code === 40100) {
        localStorage.removeItem('token')
        router.push('/login')
      }
      ElMessage.error(body.message || '请求失败')
      return Promise.reject(new Error(body.message))
    }
    return body
  },
  err => {
    ElMessage.error(err.message || '网络错误')
    return Promise.reject(err)
  }
)

export default http
