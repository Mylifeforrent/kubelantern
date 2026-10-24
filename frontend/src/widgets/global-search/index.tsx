/** 顶栏全局搜索（widgets/global-search）：跨 alerts/incidents/findings 的入口。
 *  当前收敛为跳告警工作台带 q 参数（[ASSUMPTION] 全局搜索语义随 04-api 检索端点定稿扩展）。 */
import { useState, type JSX } from 'react'
import { useNavigate } from 'react-router'
import { Icon } from '../../shared/ui/icon'

export function GlobalSearch(): JSX.Element {
  const [kw, setKw] = useState('')
  const navigate = useNavigate()

  return (
    <form
      className="gsearch"
      role="search"
      aria-label="全局搜索"
      onSubmit={(e) => {
        e.preventDefault()
        if (kw.trim()) void navigate(`/alerts?q=${encodeURIComponent(kw.trim())}`)
      }}
    >
      <Icon name="search" size={14} />
      <input
        value={kw}
        onChange={(e) => setKw(e.target.value)}
        placeholder="搜索告警、事件、发现…"
        aria-label="搜索关键词"
      />
    </form>
  )
}
