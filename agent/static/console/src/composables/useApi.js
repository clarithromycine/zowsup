import { ref } from 'vue'
import { ElMessage } from 'element-plus'

const API = ''

export function useApi() {
  const loading = ref(false)

  async function api(url, opts = {}) {
    loading.value = true
    try {
      const r = await fetch(API + url, opts)
      if (!r.ok) {
        const detail = (await r.json().catch(() => ({}))).detail || r.statusText
        throw new Error(detail)
      }
      return await r.json()
    } catch (e) {
      ElMessage.error(e.message)
      throw e
    } finally {
      loading.value = false
    }
  }

  return { api, loading }
}
