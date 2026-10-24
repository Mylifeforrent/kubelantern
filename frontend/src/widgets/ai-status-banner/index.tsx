/** NoAI 熔断全局标识（widgets/ai-status-banner，HLD §5.1 下行状态显著标识）。
 *  熔断态来自 realtime store（system 域事件；事件契约随 04-api 定稿 [ASSUMPTION]）。 */
import type { JSX } from 'react'
import { useRealtimeStore } from '../../shared/api/realtime/store'
import { Icon } from '../../shared/ui/icon'

export function AiStatusBanner(): JSX.Element | null {
  const open = useRealtimeStore((s) => s.aiCircuit === 'open')
  if (!open) return null
  return (
    <div className="ai-banner" role="alert">
      <Icon name="warn" size={13} />
      <b className="font-medium">AI 能力已熔断（NoAI 模式）</b>
      <span className="text-tx2">
        模型端点不可用，AI 解释/调查/生成任务已降级为人工排障入口；确定性链路（L1-L4）不受影响。
      </span>
    </div>
  )
}
