/** 巡检看板（P0，hifi §3.6）：集群分段器 + 统计卡 + 趋势柱图 + 策略卡 + findings 表
 *  （行内展开 AI 解释；info 级禁用 AI 按钮 —— BR-09）。 */
import { useMemo, useState, type JSX } from 'react'
import { useSearchParams } from 'react-router'
import type { ColumnDef, Row } from '@tanstack/react-table'
import { PageHeader, Card, StatCard, Kv, Bars, Empty, Aibox } from '../../shared/ui/data'
import { DataTable } from '../../shared/ui/data-table'
import { Seg, Select, Label, Textarea } from '../../shared/ui/inputs'
import { Button, Ibtn } from '../../shared/ui/button'
import { Modal } from '../../shared/ui/overlays'
import { SevChip, FindingStatusChip, AiChip } from '../../shared/ui/chips'
import { Icon } from '../../shared/ui/icon'
import {
  useClusters,
  useFindings,
  useRuns,
  usePolicies,
  useInspectionRules,
  useFindingActions,
} from './api'
import { formatDateTime, formatRelative } from '../../shared/lib/format'
import { can } from '../../shared/types/permissions'
import { useRole } from '../session'
import type { Finding } from '../../shared/api/types'

export function InspectionsPage(): JSX.Element {
  const role = useRole()
  const [params, setParams] = useSearchParams()
  const [expanded, setExpanded] = useState<number | null>(null)
  const [ignoring, setIgnoring] = useState<Finding | null>(null)
  const { data: clusterData } = useClusters()
  const clusters = clusterData?.items ?? []
  const clusterId = Number(params.get('cluster') ?? clusters[0]?.id ?? 0)
  const severity = params.get('sev') ?? undefined
  const { data: findingData } = useFindings(clusterId, severity)
  const { data: runData } = useRuns(clusterId)
  const { data: policyData } = usePolicies(clusterId || undefined)
  const { data: ruleData } = useInspectionRules()
  const actions = useFindingActions()

  const findings = useMemo(() => findingData?.items ?? [], [findingData])
  const runs = (runData?.items ?? []).filter((r) => r.cluster_id === clusterId)
  const policies = (policyData?.items ?? []).filter((p) => p.cluster_id === clusterId)
  const lastRun = runs[0]
  const stats = useMemo(() => {
    const open = findings.filter((f) => f.status === 'open').length
    const acked = findings.filter((f) => ['acknowledged', 'in_progress'].includes(f.status)).length
    const explained = findings.filter((f) => f.status === 'resolved' || f.converted_alert_id).length
    return { open, acked, explained }
  }, [findings])

  const trend = useMemo(() => {
    // 近 7 次 run 的 warn+ / info 计数；分级别计数待 run.result 提供后替换 [ASSUMPTION]
    const recent = runs.slice(0, 7).reverse()
    return recent.map((r) => {
      const warn = Math.max(1, Math.round(r.findings_count * 0.7))
      return {
        label: formatDateTime(r.started_at).slice(0, 5),
        warn,
        info: Math.max(0, r.findings_count - warn),
      }
    })
  }, [runs])
  const trendMax = trend.reduce((m, d) => Math.max(m, d.warn + d.info), 1)
  const trendData = trend.map((d) => ({ ...d, max: trendMax }))

  const columns = useMemo<ColumnDef<Finding, unknown>[]>(
    () => [
      {
        id: 'rule',
        header: '规则',
        cell: ({ row }) => (
          <div>
            <span className="mono">{row.original.rule_code}</span>
            <div className="asub">
              <Icon name="file" size={11} />#{row.original.id} ·{' '}
              {formatRelative(row.original.created_at)}
            </div>
          </div>
        ),
      },
      {
        id: 'resource',
        header: '资源',
        cell: ({ row }) => {
          const r = row.original.resource_ref
          return (
            <span className="tiny">
              {r.kind}
              {r.namespace ? ` / ${r.namespace}` : ''}
              <span className="mono block text-tx2">{r.name}</span>
            </span>
          )
        },
      },
      {
        id: 'sev',
        header: '严重度',
        cell: ({ row }) => <SevChip severity={row.original.severity} />,
      },
      {
        id: 'status',
        header: '状态',
        cell: ({ row }) => <FindingStatusChip status={row.original.status} />,
      },
      {
        id: 'ai',
        header: 'AI 解释',
        cell: ({ row }) => {
          const f = row.original
          if (f.severity === 'info')
            return (
              <span className="tiny text-dim" title="BR-09：info 只入看板不触发 AI">
                不入 AI
              </span>
            )
          return <AiChip label={f.status === 'resolved' ? '已解释' : '未解释'} />
        },
      },
      {
        id: 'acts',
        header: '',
        cell: ({ row }) => {
          const f = row.original
          return (
            <div className="rowacts">
              <Ibtn
                aria-label="认领"
                title="认领"
                disabled={!can(role, 'finding.ack') || f.status !== 'open'}
                onClick={() => actions.ack.mutate(f.id)}
              >
                <Icon name="check" size={13} />
              </Ibtn>
              <Ibtn
                aria-label="忽略"
                title="忽略（需填原因）"
                disabled={!can(role, 'finding.ignore') || f.status !== 'open'}
                onClick={() => setIgnoring(f)}
              >
                <Icon name="x" size={13} />
              </Ibtn>
              <Button
                variant="ai"
                small
                disabled={!can(role, 'finding.explain') || f.severity === 'info'}
                title={f.severity === 'info' ? 'BR-09：info 级不触发 AI 解释' : '一键 AI 解释'}
                onClick={() => actions.explain.mutate(f.id)}
              >
                <Icon name="spark" size={12} /> AI
              </Button>
            </div>
          )
        },
      },
    ],
    [role, actions],
  )

  return (
    <>
      <PageHeader
        title="巡检看板"
        sub={
          lastRun
            ? `最近巡检 ${formatRelative(lastRun.started_at)} · 规则库 ${ruleData?.total ?? 0} 条`
            : '暂无巡检执行记录'
        }
        actions={
          <Seg
            value={String(clusterId)}
            onChange={(v) =>
              setParams((p) => {
                const next = new URLSearchParams(p)
                next.set('cluster', v)
                return next
              })
            }
            ariaLabel="集群切换"
            options={clusters.map((c) => ({ value: String(c.id), label: c.name }))}
          />
        }
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <StatCard
          label="集群健康分"
          icon="radar"
          value={stats.open === 0 ? 98 : Math.max(60, 98 - stats.open * 4)}
          sub="按 open findings 折算 [ASSUMPTION]"
        />
        <StatCard label="Open findings" icon="warn" value={stats.open} sub="待认领处置" />
        <StatCard label="处置中" icon="check" value={stats.acked} sub="已认领 / 处理中" />
        <StatCard label="AI 已解释" icon="spark" value={stats.explained} sub="A1 链路产出" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <Card header="findings 趋势（近 7 次 run）" icon="radar">
          <div className="card-b">
            {trendData.length === 0 ? (
              <Empty text="暂无巡检执行记录" />
            ) : (
              <>
                <Bars
                  data={trendData}
                  ariaLabel="近 7 次巡检 findings 堆叠柱状图：warn 及以上 / info"
                />
                <div className="flex items-center gap-4 mt-3">
                  <span className="tiny text-tx2 flex items-center gap-1">
                    <i
                      className="inline-block w-2 h-2 rounded-sm"
                      style={{ background: 'var(--color-primary)' }}
                    />{' '}
                    warn 及以上
                  </span>
                  <span className="tiny text-tx2 flex items-center gap-1">
                    <i
                      className="inline-block w-2 h-2 rounded-sm"
                      style={{ background: 'rgba(7,121,164,.45)' }}
                    />{' '}
                    info
                  </span>
                  <span className="tiny text-dim ml-auto">warn+ 达标转告警（BR-09）</span>
                </div>
              </>
            )}
          </div>
        </Card>
        <Card header="巡检策略" icon="gear">
          <div className="card-b flex flex-col gap-3">
            {policies.length === 0 && <Empty text="该集群暂无巡检策略" />}
            {policies.map((p) => (
              <Kv
                key={p.id}
                rows={[
                  ['名称', `${p.name}${p.enabled ? '' : '（已停用）'}`],
                  ['调度', <span className="mono">{p.schedule}</span>],
                  ['规则集', `${p.rule_ids.length} 条规则`],
                  ['ai_explain_level', <span className="mono">{p.ai_explain_level}</span>],
                  ['转告警', 'warning 及以上（BR-09）'],
                ]}
              />
            ))}
          </div>
        </Card>
      </div>

      <Card
        header="Findings"
        icon="warn"
        right={<span className="tiny text-dim num">共 {findingData?.total ?? 0} 条</span>}
      >
        <div className="fbar" role="group" aria-label="findings 筛选">
          <Select
            value={params.get('sev') ?? ''}
            onChange={(v) =>
              setParams((p) => {
                const next = new URLSearchParams(p)
                if (v) next.set('sev', v)
                else next.delete('sev')
                return next
              })
            }
            placeholder="全部严重度"
            ariaLabel="严重度筛选"
            options={[
              { value: 'critical', label: 'critical' },
              { value: 'warning', label: 'warning' },
              { value: 'info', label: 'info' },
            ]}
          />
          <span className="count">
            {findings.length} / {findingData?.total ?? 0}
          </span>
        </div>
        <DataTable
          ariaLabel="巡检发现列表"
          columns={columns}
          data={findings}
          onRowClick={(row: Row<Finding>) =>
            setExpanded((e) => (e === row.original.id ? null : row.original.id))
          }
          rowClass={(row: Row<Finding>) => (expanded === row.original.id ? 'hl' : undefined)}
          emptyText="该集群暂无 findings"
        />
        {findings
          .filter((f) => f.id === expanded)
          .map((f) => (
            <div key={f.id} className="px-4 pb-4">
              <Aibox
                title="AI 解释 · 展开行"
                footnote={
                  <>
                    <Icon name="shield" size={12} /> 输入已脱敏（BR-01）· 本地模型优先（BR-12）·
                    预算内调用（BR-03）
                  </>
                }
              >
                {f.severity === 'info' ? (
                  '该 finding 为 info 级：不入 AI 解释链路（BR-09）。'
                ) : (
                  <div className="flex flex-col gap-1">
                    <div>原始错误：{JSON.stringify(f.raw_error)}</div>
                    <div className="text-tx2">
                      解释生成中态与 NoAI 降级态：AI
                      任务经审批/预算链路后回填此处；模型不可用时透出原始错误与人工排障入口。
                    </div>
                  </div>
                )}
              </Aibox>
              {f.ignored_reason && (
                <p className="tiny text-dim mt-2">忽略原因：{f.ignored_reason}</p>
              )}
            </div>
          ))}
      </Card>

      {ignoring && <IgnoreModal finding={ignoring} onClose={() => setIgnoring(null)} />}
    </>
  )
}

function IgnoreModal({ finding, onClose }: { finding: Finding; onClose: () => void }): JSX.Element {
  const [reason, setReason] = useState('')
  const { ignore } = useFindingActions()
  return (
    <Modal
      open
      onClose={onClose}
      label={`忽略发现 ${finding.rule_code}`}
      title={
        <>
          <Icon name="x" size={15} className="text-tx2" /> 忽略发现 · {finding.rule_code}
        </>
      }
      footer={
        <>
          <Button onClick={onClose}>取消</Button>
          <Button
            variant="primary"
            disabled={!reason}
            onClick={() => ignore.mutate({ id: finding.id, reason }, { onSuccess: onClose })}
          >
            提交忽略
          </Button>
        </>
      }
    >
      <Label htmlFor="ignore-reason">忽略原因（必填，D-10）</Label>
      <Textarea
        id="ignore-reason"
        rows={3}
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="例如：开发联调镜像，随版本清理"
      />
    </Modal>
  )
}
