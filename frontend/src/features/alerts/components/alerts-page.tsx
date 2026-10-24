/** 告警工作台（P0 重点页，hifi §3.1）：管道四步卡 + 统计卡 + 筛选条 + 告警表 + 详情抽屉。
 *  实时性：SSE alert.updated 精确失效（handlers.ts）；断连时兜底轮询 10s [ASSUMPTION]。 */
import { useMemo, type JSX } from 'react'
import { useSearchParams } from 'react-router'
import type { ColumnDef, Row } from '@tanstack/react-table'
import { useRole } from '../../session'
import { useAlerts, useAckAlert, useCloseAlert } from '../api'
import { deriveAlertStats, dedupSummary } from '../stats'
import { AlertDetailDrawer } from './alert-drawer'
import { PageHeader, Card, StatCard, PStepCard } from '../../../shared/ui/data'
import { DataTable } from '../../../shared/ui/data-table'
import { Seg, Select, Input } from '../../../shared/ui/inputs'
import { Ibtn } from '../../../shared/ui/button'
import { SevChip, AlertStatusChip } from '../../../shared/ui/chips'
import { Icon } from '../../../shared/ui/icon'
import { useRealtimeStore } from '../../../shared/api/realtime/store'
import { formatDateTime } from '../../../shared/lib/format'
import { can } from '../../../shared/types/permissions'
import type { Alert } from '../../../shared/api/types'

export function AlertsPage(): JSX.Element {
  const role = useRole()
  const [params, setParams] = useSearchParams()
  const connected = useRealtimeStore((s) => s.connection === 'open')

  const filters = {
    severity: params.get('severity') ?? undefined,
    status: params.get('status') ?? undefined,
    q: params.get('q') ?? undefined,
    limit: 200,
  }
  const { data, isFetching } = useAlerts(filters)
  const alerts = useMemo(() => data?.items ?? [], [data])
  const stats = useMemo(() => deriveAlertStats(alerts), [alerts])
  const ack = useAckAlert()
  const close = useCloseAlert()

  const setParam = (k: string, v: string | null) =>
    setParams((p) => {
      const next = new URLSearchParams(p)
      if (v === null || v === '') next.delete(k)
      else next.set(k, v)
      return next
    })

  const columns = useMemo<ColumnDef<Alert, unknown>[]>(
    () => [
      {
        id: 'severity',
        header: '严重度',
        cell: ({ row }) => <SevChip severity={row.original.severity} />,
      },
      {
        id: 'title',
        header: '告警 / 降噪归因',
        cell: ({ row }) => (
          <div className="min-w-0">
            <div className="atitle truncate">{row.original.title ?? row.original.fingerprint}</div>
            <div className="asub">
              <Icon name="inbox" size={11} />
              {dedupSummary(row.original)}
              {row.original.occurrence_count > 1 && (
                <span className="chip sev-p2 num ml-1">×{row.original.occurrence_count}</span>
              )}
            </div>
          </div>
        ),
      },
      {
        id: 'fingerprint',
        header: 'Fingerprint',
        cell: ({ row }) => (
          <span
            className="mono text-tx2 block max-w-[180px] truncate"
            title={row.original.fingerprint}
          >
            {row.original.fingerprint}
          </span>
        ),
      },
      {
        id: 'enrich',
        header: '富化',
        cell: ({ row }) => {
          const e = row.original.enrichments ?? {}
          const team = e.team as string | undefined
          const service = e.service as string | undefined
          const namespace = e.namespace as string | undefined
          const parts = [
            team !== undefined && `团队 ${team}`,
            service !== undefined && service,
            namespace !== undefined && `ns:${namespace}`,
          ].filter((p): p is string => typeof p === 'string')
          return <span className="tiny text-tx2">{parts.length > 0 ? parts.join(' · ') : '—'}</span>
        },
      },
      {
        id: 'status',
        header: '状态',
        cell: ({ row }) => <AlertStatusChip status={row.original.status} />,
      },
      {
        id: 'last',
        header: '最近发生',
        cell: ({ row }) => (
          <span className="tiny text-tx2 num">{formatDateTime(row.original.last_occurred_at)}</span>
        ),
      },
      {
        id: 'acts',
        header: '',
        cell: ({ row }) => (
          <div className="rowacts" onClick={(e) => e.stopPropagation()}>
            <Ibtn
              aria-label="认领告警"
              title="认领（Ack）"
              disabled={!can(role, 'alert.ack') || row.original.status === 'resolved'}
              onClick={() => ack.mutate(row.original.id)}
            >
              <Icon name="check" size={13} />
            </Ibtn>
            <Ibtn
              aria-label="关闭告警"
              title="关闭"
              disabled={!can(role, 'alert.close') || row.original.status === 'resolved'}
              onClick={() => close.mutate(row.original.id)}
            >
              <Icon name="x" size={13} />
            </Ibtn>
          </div>
        ),
      },
    ],
    [role, ack, close],
  )

  const onRowClick = (row: Row<Alert>) => setParam('selected', String(row.original.id))

  return (
    <>
      <PageHeader
        title="告警工作台"
        sub={
          <>
            接入 → 去重 → 富化 → 关联 全链路降噪视图
            {connected ? ' · 实时更新中' : ' · 实时通道未连接（10s 兜底轮询）'}
          </>
        }
      />

      {/* 管道四步卡（激活态 = 该步有新增待处理量） */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <PStepCard
          label="① 接入"
          icon="inbox"
          value={stats.pipeline.received}
          sub="待处理接收量"
          active={stats.pipeline.received > 0}
          arrow
        />
        <PStepCard
          label="② 去重"
          icon="filter"
          value={stats.pipeline.dedup}
          sub={`合并抑制 ${stats.dedupSaved} 次`}
          arrow
        />
        <PStepCard
          label="③ 富化"
          icon="link"
          value={stats.pipeline.enrich}
          sub="已补全团队/影响面"
          arrow
        />
        <PStepCard
          label="④ 关联"
          icon="layers"
          value={stats.pipeline.correlate}
          sub="命中关联规则"
        />
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <StatCard
          label="待处理告警"
          icon="siren"
          value={stats.pending}
          sub={
            <>
              <b className="up">实时</b> · 演示数据
            </>
          }
        />
        <StatCard
          label="去重抑制"
          icon="filter"
          value={stats.dedupSaved}
          sub="同指纹合并计数节省"
        />
        <StatCard
          label="P1 活跃"
          icon="warn"
          value={stats.p12Active}
          sub={<span className="warm">需优先响应</span>}
        />
        <StatCard
          label="维护窗口抑制"
          icon="shield"
          value={stats.suppressed}
          sub="窗口结束未恢复将重新入管道（BR-07）"
        />
      </div>

      <Card
        header="告警列表"
        icon="siren"
        right={
          <span className="tiny text-dim num">
            {isFetching ? '刷新中…' : `共 ${data?.total ?? 0} 条`}
          </span>
        }
        bodyClass="pb-2"
      >
        <div className="fbar" role="group" aria-label="告警筛选">
          <Seg
            value={params.get('severity') ?? ''}
            onChange={(v) => setParam('severity', v)}
            ariaLabel="严重度分段筛选"
            options={[
              { value: '', label: '全部' },
              { value: 'critical', label: 'P1' },
              { value: 'warning', label: 'P3' },
              { value: 'info', label: 'P4' },
            ]}
          />
          <Select
            value={params.get('status') ?? ''}
            onChange={(v) => setParam('status', v)}
            placeholder="全部状态"
            ariaLabel="状态筛选"
            options={[
              { value: 'notified', label: '已通知' },
              { value: 'correlated', label: '已关联' },
              { value: 'deduplicated', label: '已去重' },
              { value: 'suppressed', label: '已抑制' },
              { value: 'resolved', label: '已关闭' },
            ]}
          />
          <Input
            value={params.get('q') ?? ''}
            onChange={(e) => setParam('q', e.target.value)}
            placeholder="搜索标题 / fingerprint"
            aria-label="搜索告警"
            className="w-52"
          />
          <span className="count">
            {alerts.length} / {data?.total ?? 0}
          </span>
        </div>
        <DataTable
          ariaLabel="告警列表"
          columns={columns}
          data={alerts}
          onRowClick={onRowClick}
          emptyText="没有匹配的告警"
        />
      </Card>

      <AlertDetailDrawer />
    </>
  )
}
