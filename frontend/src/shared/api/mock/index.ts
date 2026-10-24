/** mock 装配入口：providers 初始化时调用（仅 VITE_USE_MOCK=1 生效） */
import { setAiCircuit } from '../realtime/store'
import { seed } from './fixtures'
import { startMockDemoFeed } from './realtime'
import { installMockFetch } from './server'

export function installMock(): boolean {
  if (import.meta.env.VITE_USE_MOCK !== '1') return false
  seed()
  installMockFetch()
  startMockDemoFeed()
  // NoAI 熔断演示事件（HLD §5.1 显著标识）
  window.addEventListener('huntai:ai-circuit', (e) => {
    setAiCircuit((e as CustomEvent<string>).detail === 'open' ? 'open' : 'normal')
  })
  return true
}
