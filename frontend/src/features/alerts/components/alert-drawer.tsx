/** 告警详情抽屉（hifi §3.2）：5 tab（详情/原始 Payload/富化字段/AI 解释/关联事件）
 *  + 底部操作条（认领/转事件/抑制建议 + 审计提示）。 */
import type { JSX } from 'react'
import { useSearchParams } from 'react-router'
import { Icon } from '../../../shared/ui/icon'
import { Tabs, Kv, CodeBlock, Aibox, Empty, LinkList } from '../../../shared/ui/data'
import { Drawer } from '../../../shared/ui/overlays'
import { Button, Ibtn } from '../../../shared/ui/button'
import { AlertStatusChip, SevChip } from '../../../shared/ui/chips'
import { formatDateTime } from '../../../shared/lib/format'
import { can } from '../../../shared/types/permissions'
import { useRole } from '../../session'
import { useAlert, useAlertExplanations, useAckAlert, useCloseAlert, useConvertAlert } from '../api'
import { dedupSummary } from '../stats'
import { SuppressModal } from './suppress-modal'

const TABS = [
  { key: 'detail', label: '详情' },
  { key: 'payload', label: '原始 Payload' },
  { key: 'enrich', label: '富化字段' },
  { key: 'ai', label: 'AI 解释' },
  { key: 'related', label: '关联事件' },
]

export function AlertDetailDrawer(): JSX.Element | null {
  const [params, setParams] = useSearchParams()
  const selected = params.get('selected')
  const tab = params.get('tab') ?? 'detail'
  const id = selected ? Number(selected) : null
  const role = useRole()
  const { data: alert } = useAlert(id)
  const { data: explanations } = useAlertExplanations(id, tab === 'ai')
  const ack = useAckAlert()
  const close = useCloseAlert()
  const convert = useConvertAlert()

  if (!alert) return null
  const setSearch = (patch: Record<string, string | null>) => {
    const next = new URLSearchParams(params)
    for (const [k, v] of Object.entries(patch)) {
      if (v === null) next.delete(k)
      else next.set(k, v)
    }
    setParams(next, { replace: true })
  }
  const closeDrawer = () => setSearch({ selected: null, tab: null })
  const noAi = tab === 'ai' && (explanations === undefined || explanations.items.length === 0)

  return (
    <Drawer
      open
      onClose={closeDrawer}
      label={`告警详情 ${alert.id}`}
      header={
        <div className="flex items-start gap-2 flex-1 min-w-0">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <SevChip severity={alert.severity} />
              <span className="atitle text-[14px] truncate">
                {alert.title ?? alert.fingerprint}
              </span>
            </div>
            <div className="flex items-center gap-2 mt-1">
              <AlertStatusChip status={alert.status} />
              <span className="mono text-dim">#{alert.id}</span>
              <span className="tiny text-tx2">合并 ×{alert.occurrence_count}</span>
            </div>
          </div>
          <Ibtn aria-label="关闭抽屉" onClick={closeDrawer}>
            <Icon name="x" size={14} />
          </Ibtn>
        </div>
      }
      tabs={<Tabs tabs={TABS} active={tab} onChange={(k) => setSearch({ tab: k })} />}
      footer={
        <>
          <Button
            variant="primary"
            disabled={!can(role, 'alert.ack') || alert.status === 'resolved'}
            onClick={() => id !== null && ack.mutate(id)}
          >
            <Icon name="check" size={14} /> 认领（Ack）
          </Button>
          <Button
            disabled={!can(role, 'alert.convert') || alert.status === 'resolved'}
            onClick={() =>
              id !== null &&
              convert.mutate({
                id,
                body: { title: alert.title ?? alert.fingerprint, severity: 'P2' },
              })
            }
          >
            <Icon name="zap" size={14} /> 转事件
          </Button>
          <Button
            disabled={!can(role, 'alert.close') || alert.status === 'resolved'}
            onClick={() => id !== null && close.mutate(id)}
          >
            <Icon name="x" size={14} /> 关闭
          </Button>
          <SuppressButton alertId={id} disabled={!can(role, 'alert.suppress')} />
          <div className="flex-1" />
          <span className="tiny text-dim flex items-center gap-1">
            <Icon name="clock" size={12} /> 全部操作已留痕（BR-10）
          </span>
        </>
      }
    >
      <div className="p-4 flex flex-col gap-4">
        {tab === 'detail' && (
          <>
            <Kv
              rows={[
                ['fingerprint', <span className="mono">{alert.fingerprint}</span>],
                ['状态', <AlertStatusChip status={alert.status} />],
                ['合并计数', <span className="num">{alert.occurrence_count}</span>],
                ['首次发生', formatDateTime(alert.first_occurred_at)],
                ['最近发生', formatDateTime(alert.last_occurred_at)],
                ['认领人', alert.assignee_id ? `#${alert.assignee_id}` : '未认领'],
              ]}
            />
            {/* 降噪归因（teal 信息框；可视化深化 [TBD-UX] 沿用交互 §7） */}
            <Aibox
              variant="info"
              title="降噪归因"
              footnote={
                <>
                  <Icon name="inbox" size={12} /> 归因由管道状态与合并计数派生
                </>
              }
            >
              {dedupSummary(alert)}
            </Aibox>
          </>
        )}
        {tab === 'payload' && (
          <CodeBlock
            ariaLabel="原始上报内容快照"
            text={JSON.stringify(alert.raw_payload ?? {}, null, 2)}
          />
        )}
        {tab === 'enrich' && (
          <Kv
            rows={Object.entries({ ...(alert.enrichments ?? {}) }).map(([k, v]) => [
              k,
              <span className="mono">{String(v)}</span>,
            ])}
          />
        )}
        {tab === 'ai' && (
          <>
            {noAi && (
              <Aibox
                variant="warn"
                title="暂无 AI 解释"
                footnote={
                  <>
                    <Icon name="clock" size={12} /> BR-09：warning 及以上且策略 ai_explain_level
                    命中时自动触发
                  </>
                }
              >
                该告警当前没有 AI 解释：可在巡检看板对命中 finding 触发解释，或等待 P1 AI
                解释链路生效。若平台处于 NoAI 熔断态，请走人工排障入口。
              </Aibox>
            )}
            {explanations?.items.map((e) => (
              <Aibox
                key={e.id}
                title="AI 诊断解释"
                footnote={
                  <>
                    <Icon name="shield" size={12} /> 输入已脱敏（{e.sanitized_input_digest}）· 模型{' '}
                    {e.model} · {e.tokens} tokens
                  </>
                }
              >
                <div className="flex flex-col gap-2">
                  {e.output.noai === true ? (
                    <div className="text-tx2">
                      NoAI 降级：当前模型不可用或已熔断，已保留原始错误供人工排障。
                    </div>
                  ) : (
                    <div className="whitespace-pre-wrap text-[12.5px] leading-relaxed">
                      {typeof e.output.diagnosis === 'string'
                        ? e.output.diagnosis
                        : typeof e.output.summary === 'string'
                          ? e.output.summary
                          : ''}
                    </div>
                  )}
                  {Array.isArray(e.output.suggestions) && (
                    <ul className="list-disc pl-5 flex flex-col gap-1">
                      {e.output.suggestions.map((s, i) => (
                        <li key={i}>{String(s)}</li>
                      ))}
                    </ul>
                  )}
                </div>
              </Aibox>
            ))}
          </>
        )}
        {tab === 'related' && (
          <LinkList>
            <Empty text="演示数据未生成关联事件" sub="事件关联在候选事件确认立项后建立（BR-04）" />
          </LinkList>
        )}
      </div>
    </Drawer>
  )
}

function SuppressButton({
  alertId,
  disabled,
}: {
  alertId: number | null
  disabled: boolean
}): JSX.Element {
  const [params, setParams] = useSearchParams()
  return (
    <>
      <Button
        disabled={disabled || alertId === null}
        onClick={() =>
          setParams((p) => {
            const next = new URLSearchParams(p)
            next.set('suppress', String(alertId))
            return next
          })
        }
      >
        <Icon name="x" size={14} /> 抑制建议
      </Button>
      {params.get('suppress') && <SuppressModal alertId={Number(params.get('suppress'))} />}
    </>
  )
}
