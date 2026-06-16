import { ref, onUnmounted } from 'vue'

export function useWebSocket() {
  const ws = ref(null)
  const wsUrl = ref('')
  const connected = ref(false)

  function connect(url, handlers = {}) {
    if (ws.value && wsUrl.value === url) return
    close()

    wsUrl.value = url
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:'
    ws.value = new WebSocket(`${proto}//${location.host}${url}`)

    ws.value.onopen = () => {
      connected.value = true
      handlers.onopen?.()
    }
    ws.value.onmessage = (e) => handlers.onmessage?.(e)
    ws.value.onclose = () => {
      connected.value = false
      if (ws.value) handlers.onclose?.()
    }
    ws.value.onerror = () => handlers.onerror?.()
  }

  function close() {
    if (ws.value) {
      ws.value.close()
      ws.value = null
      wsUrl.value = ''
      connected.value = false
    }
  }

  onUnmounted(close)

  return { ws, connected, connect, close }
}
