/** 事件响应列表（P2，hifi §3.4）+ 事件详情（hifi §3.5：状态机步进条 + 时间线 + 三支撑卡）。
 *  状态机 6 态（领域 §6）：open→acknowledged→mitigated→resolved→closed，open→cancelled 误报。 */
import { useState, type JSX } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import type { ColumnDef } from '@tanstack/react-table'
import {
  PageHeader,
  Card,
  Empty,
  Stepper,
  Timeline,
  Kv,
  CodeBlock,
  LinkItem,
  LinkList,
  type TimelineKind,
} from '../../shared/ui/data'
import { DataTable } from '../../shared/ui/data-table'
import { Button } from '../../shared/ui/button'
import { Modal } from '../../shared/ui/overlays'
import { Input } from '../../shared/ui/inputs'
import { IncidentSevChip, IncidentStatusChip, OkChip, SevChip } from '../../shared/ui/chips'
import { Icon } from '../../shared/ui/icon'
import {
  useIncidents,
  useIncident,
  useIncidentAction,
  useAddTimelineNote,
  useStatusPageSync,
  type IncidentAction,
} from './api'
import { formatDateTime, formatRelative } from '../../shared/lib/format'
import { can } from '../../shared/types/permissions'
import { useRole } from '../session'
import type { Incident } from '../../shared/api/types'

const STEPS = [
  { key: 'open', label: '立项' },
  { key: 'acknowledged', label: '已确认' },
  { key: 'mitigated', label: '已止血' },
  { key: 'resolved', label: '已恢复' },
  { key: 'closed', label: '已关闭' },
]

/** 主按钮文案随状态机切换（03-frontend-design §5.2） */
const NEXT_ACTION: Partial<Record<Incident['status'], { action: IncidentAction; label: string }>> =
  {
    open: { action: 'acknowledge', label: '确认处理' },
    acknowledged: { action: 'mitigate', label: '止血完成' },
    mitigated: { action: 'resolve', label: '根因恢复' },
    resolved: { action: 'close', label: '关闭事件' },
  }

export function IncidentsPage(): JSX.Element {
  const navigate = useNavigate()
  const { data } = useIncidents()
  const incidents = data?.items ?? []

  const columns = useMemoListColumns()
  return (
    <>
      <PageHeader
        title="事件响应"
        sub="候选确认 / 人工立项 → 状态机闭环 → 状态页联动 → 复盘（L3）"
      />
      <Card
        header="事件列表"
        icon="zap"
        right={<span className="tiny text-dim num">共 {data?.total ?? 0} 起</span>}
      >
        <DataTable
          ariaLabel="事件列表"
          columns={columns}
          data={incidents}
          onRowClick={(row) => void navigate(`/incidents/${row.original.id}`)}
          emptyText="暂无事件"
        />
      </Card>
    </>
  )
}

function useMemoListColumns() {
  const columns: ColumnDef<Incident, unknown>[] = [
    {
      id: 'incident',
      header: '事件',
      cell: ({ row }) => (
        <div>
          <span className="mono text-tx2">INC-{String(row.original.id).padStart(4, '0')}</span>
          <div className="atitle">{row.original.title}</div>
        </div>
      ),
    },
    {
      id: 'sev',
      header: '严重度',
      cell: ({ row }) => <IncidentSevChip severity={row.original.severity} />,
    },
    {
      id: 'status',
      header: '状态',
      cell: ({ row }) => <IncidentStatusChip status={row.original.status} />,
    },
    {
      id: 'assignee',
      header: '值班人',
      cell: ({ row }) =>
        row.original.assignee_id ? (
          `#${row.original.assignee_id}`
        ) : (
          <span className="warm">待认领</span>
        ),
    },
    {
      id: 'statuspage',
      header: '状态页',
      cell: ({ row }) =>
        row.original.status_page_sync ? (
          <OkChip label="已同步" />
        ) : (
          <span className="text-tx2">—</span>
        ),
    },
    {
      id: 'created',
      header: '创建时间',
      cell: ({ row }) => (
        <span className="tiny text-tx2 num">{formatDateTime(row.original.created_at)}</span>
      ),
    },
  ]
  return columns
}

export function IncidentDetailPage(): JSX.Element {
  const { incidentId } = useParams()
  const id = incidentId ? Number(incidentId) : null
  const role = useRole()
  const { data: incident } = useIncident(id)
  const action = useIncidentAction()
  const addNote = useAddTimelineNote()
  const { sync } = useStatusPageSync()
  const [cancelling, setCancelling] = useState(false)
  const [note, setNote] = useState('')

  if (!incident) {
    return (
      <Card>
        <Empty
          icon="zap"
          text="事件不存在（或无权访问）"
          sub="越权访问一律 404 防资源探测（04-backend §4.4）"
        />
      </Card>
    )
  }
  const next = NEXT_ACTION[incident.status]
  const timeline = incident.timeline ?? []
  const kindOf = (k: string): TimelineKind =>
    k === 'manual_note' ? 'man' : k === 'notification' ? 'esc' : k.includes('ai') ? 'ai' : 'auto'

  return (
    <>
      <div className="ph">
        <Link to="/incidents" className="ibtn mt-0.5" aria-label="返回事件列表">
          <Icon name="chl" size={15} />
        </Link>
        <div className="min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h1>
              INC-{String(incident.id).padStart(4, '0')} · {incident.title}
            </h1>
            <IncidentSevChip severity={incident.severity} />
            <IncidentStatusChip status={incident.status} />
          </div>
          <p>
            团队 {incident.team ?? '—'} · 来源{' '}
            {incident.source === 'correlation' ? '关联规则' : '人工立项'} · 创建{' '}
            {formatRelative(incident.created_at)}
          </p>
        </div>
        <div className="flex-1" />
        <div className="flex items-center gap-2">
          {next && can(role, 'incident.manage') && (
            <Button
              variant="primary"
              disabled={action.isPending}
              onClick={() => id !== null && action.mutate({ id, action: next.action })}
            >
              <Icon name="check" size={14} /> {next.label}
            </Button>
          )}
          {incident.status === 'open' && can(role, 'incident.manage') && (
            <Button variant="danger" onClick={() => setCancelling(true)}>
              误报关闭
            </Button>
          )}
          <Button variant="ai" disabled title="P3：发起 Agent 调查（A2）">
            <Icon name="spark" size={14} /> 发起调查 <span className="tag pu">P3</span>
          </Button>
        </div>
      </div>

      <Card className="mb-4">
        <div className="p-4">
          <Stepper
            steps={STEPS}
            current={incident.status === 'cancelled' ? 'cancelled' : incident.status}
          />
          {incident.status === 'cancelled' && (
            <p className="tiny text-dim mt-2">该事件已误报关闭：{incident.cancelled_reason}</p>
          )}
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card header="事件时间线" icon="clock">
          <div className="card-b flex flex-col gap-4">
            <Timeline
              items={timeline.map((t, i) => ({
                key: `${i}-${t.occurred_at}`,
                kind: kindOf(t.kind),
                time: `${formatDateTime(t.occurred_at)} · ${t.kind}`,
                text: t.summary,
              }))}
            />
            {timeline.length === 0 && <Empty text="暂无时间线条目" />}
            <form
              className="flex items-center gap-2"
              onSubmit={(e) => {
                e.preventDefault()
                if (note.trim() && id !== null) {
                  addNote.mutate({ id, note: note.trim() })
                  setNote('')
                }
              }}
            >
              <Input
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="添加处理记录…"
                aria-label="处理记录内容"
                className="flex-1"
              />
              <Button small type="submit" disabled={!note.trim() || !can(role, 'incident.manage')}>
                <Icon name="plus" size={12} /> 记录
              </Button>
            </form>
          </div>
        </Card>

        <div className="flex flex-col gap-4">
          <Card header="值班与升级状态" icon="bell">
            <div className="card-b">
              <LinkList>
                <LinkItem
                  icon="bell"
                  readOnly
                  right={<span className="tiny text-dim">一级 · IM</span>}
                >
                  当班主班 · 已投递{' '}
                  {formatRelative(incident.acknowledged_at ?? incident.created_at)}
                </LinkItem>
                <LinkItem
                  icon="shield"
                  readOnly
                  right={<span className="tiny text-dim">BR-08 留痕</span>}
                >
                  升级链各级投递与 Ack 留痕见通知记录审计
                </LinkItem>
              </LinkList>
            </div>
          </Card>

          <Card
            header="状态页同步"
            icon="file"
            right={
              incident.status_page_sync ? (
                <OkChip label="已同步" />
              ) : (
                <span className="tiny text-dim">未同步</span>
              )
            }
          >
            <div className="card-b flex items-center gap-2">
              {can(role, 'incident.status-page') && (
                <Button
                  small
                  onClick={() =>
                    id !== null && sync.mutate({ id, undo: incident.status_page_sync })
                  }
                >
                  {incident.status_page_sync ? '撤回同步' : '同步状态页'}
                </Button>
              )}
              <span className="tiny text-dim">P1/P2 自动同步，人工可撤回（BR-06）</span>
            </div>
          </Card>

          <Card header="关联告警" icon="link">
            <div className="card-b">
              {(incident.related_alerts ?? []).length === 0 ? (
                <Empty text="暂无关联告警" />
              ) : (
                <LinkList>
                  {(incident.related_alerts ?? []).map((a) => (
                    <LinkItem
                      key={a.id}
                      icon="siren"
                      onClick={() => window.location.assign(`/alerts?selected=${a.id}`)}
                    >
                      <span className="atitle truncate">{a.title ?? a.fingerprint}</span>
                      <SevChip severity={a.severity} />
                    </LinkItem>
                  ))}
                </LinkList>
              )}
            </div>
          </Card>

          <Card header="复盘报告" icon="file">
            <div className="card-b">
              <Kv
                rows={[
                  ['生成时机', 'P1/P2 事件关闭时生成模板（L3 链路）'],
                  ['状态', <span className="tiny text-dim">事件未关闭</span>],
                ]}
              />
            </div>
          </Card>
        </div>
      </div>

      {cancelling && (
        <CancelModal
          onClose={() => setCancelling(false)}
          onSubmit={(reason) => {
            if (id !== null)
              action.mutate({ id, action: 'cancel', body: { cancelled_reason: reason } })
            setCancelling(false)
          }}
        />
      )}
    </>
  )
}

function CancelModal({
  onClose,
  onSubmit,
}: {
  onClose: () => void
  onSubmit: (reason: string) => void
}): JSX.Element {
  const [reason, setReason] = useState('')
  return (
    <Modal
      open
      onClose={onClose}
      label="误报关闭"
      title={
        <>
          <Icon name="warn" size={15} className="text-tx2" /> 误报关闭（原因必填，D-10）
        </>
      }
      footer={
        <>
          <Button onClick={onClose}>取消</Button>
          <Button variant="danger" disabled={!reason} onClick={() => onSubmit(reason)}>
            确认误报关闭
          </Button>
        </>
      }
    >
      <CodeBlock text="状态机迁移：open → cancelled（记录原因后不可逆）" ariaLabel="状态机说明" />
      <Input
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="误报原因，例如：变更窗口内预期告警"
        aria-label="误报原因"
      />
    </Modal>
  )
}
