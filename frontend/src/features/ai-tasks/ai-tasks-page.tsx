/** AI 任务中心（P1 重点页，hifi §3.7）：预算统计卡 + 任务表（预算双维度进度条、
 *  pending_approval 行高亮）+ 审批 Modal + 调用链 Modal（BR-02/03/05/10）。 */
import { useMemo, useState, type JSX } from 'react'
import type { ColumnDef, Row } from '@tanstack/react-table'
import {
  PageHeader,
  Card,
  StatCard,
  Kv,
  CodeBlock,
  BudgetBar,
  Empty,
  LinkItem,
  LinkList,
} from '../../shared/ui/data'
import { DataTable } from '../../shared/ui/data-table'
import { Button, Ibtn } from '../../shared/ui/button'
import { Modal } from '../../shared/ui/overlays'
import { AiTaskStatusChip, AiChip } from '../../shared/ui/chips'
import { Icon } from '../../shared/ui/icon'
import { useAiTasks, useAiTaskActions, useCallLogs } from './api'
import {
  formatDateTime,
  formatNumber,
  formatPercent,
  formatRelative,
} from '../../shared/lib/format'
import { can } from '../../shared/types/permissions'
import { useRole } from '../session'
import type { AITask } from '../../shared/api/types'

const TYPE_LABELS: Record<AITask['type'], string> = {
  explain: 'AI 解释（A1）',
  investigate: 'Agent 调查（A2）',
  workflow_gen: 'Workflow 生成（A3）',
}

export function AiTasksPage(): JSX.Element {
  const role = useRole()
  const [approving, setApproving] = useState<AITask | null>(null)
  const [callLogOf, setCallLogOf] = useState<AITask | null>(null)
  const { data } = useAiTasks()
  const tasks = useMemo(() => data?.items ?? [], [data])
  const actions = useAiTaskActions()

  // 预算统计：契约草案未提供 AI 预算统计端点，以下为当页列表的展示聚合 [ASSUMPTION]
  const stats = useMemo(() => {
    const pending = tasks.filter((t) => t.status === 'pending_approval').length
    const calls = tasks.reduce((n, t) => n + t.calls_used, 0)
    const tokens = tasks.reduce((n, t) => n + t.tokens_used, 0)
    const budgetCalls = tasks[0]?.budget.max_calls ?? 40
    const budgetTokens = tasks[0]?.budget.max_output_tokens ?? 100_000
    return {
      calls,
      tokens,
      pending,
      localRatio: 1, // 演示数据全部为本地模型（BR-12）
      callRatio: calls / Math.max(1, budgetCalls * tasks.length),
      tokenRatio: tokens / Math.max(1, budgetTokens * tasks.length),
    }
  }, [tasks])

  const columns = useMemo<ColumnDef<AITask, unknown>[]>(
    () => [
      {
        id: 'task',
        header: '任务',
        cell: ({ row }) => (
          <div>
            <span className="mono">#{row.original.id}</span>
            <div className="asub">
              <Icon name="user" size={11} />
              by #{row.original.requested_by} · {formatRelative(row.original.created_at)}
            </div>
          </div>
        ),
      },
      {
        id: 'type',
        header: '类型',
        cell: ({ row }) => <AiChip label={TYPE_LABELS[row.original.type] ?? row.original.type} />,
      },
      {
        id: 'obj',
        header: '对象',
        cell: ({ row }) => {
          const t = row.original
          const ref = t.finding_id
            ? `finding #${t.finding_id}`
            : t.incident_id
              ? `事件 #${t.incident_id}`
              : '—'
          return <span className="tiny">{ref}</span>
        },
      },
      {
        id: 'model',
        header: '模型',
        cell: () => <span className="tiny text-tx2">本地优先（BR-12）</span>,
      },
      {
        id: 'budget',
        header: '预算（calls / tokens）',
        cell: ({ row }) => {
          const t = row.original
          const callRatio = t.budget.max_calls > 0 ? t.calls_used / t.budget.max_calls : 0
          const tokenRatio =
            t.budget.max_output_tokens > 0 ? t.tokens_used / t.budget.max_output_tokens : 0
          return (
            <div className="flex flex-col gap-1">
              <span className="flex items-center gap-2">
                <BudgetBar ratio={callRatio} />
                <span className="tiny text-tx2 num">
                  {t.calls_used}/{t.budget.max_calls} · {formatPercent(callRatio)}
                </span>
              </span>
              <span className="flex items-center gap-2">
                <BudgetBar ratio={tokenRatio} />
                <span className="tiny text-tx2 num">
                  {formatNumber(t.tokens_used)}/{formatNumber(t.budget.max_output_tokens)} ·{' '}
                  {formatPercent(tokenRatio)}
                </span>
              </span>
            </div>
          )
        },
      },
      {
        id: 'status',
        header: '状态',
        cell: ({ row }) => <AiTaskStatusChip status={row.original.status} />,
      },
      {
        id: 'acts',
        header: '',
        cell: ({ row }) => {
          const t = row.original
          return (
            <div className="rowacts">
              <Ibtn
                aria-label="查看调用链"
                title="调用链审计（BR-10，不可删改）"
                onClick={() => setCallLogOf(t)}
              >
                <Icon name="term" size={13} />
              </Ibtn>
              {t.status === 'pending_approval' && (
                <Button
                  variant="ai"
                  small
                  disabled={!can(role, 'ai.approve')}
                  onClick={() => setApproving(t)}
                >
                  <Icon name="check" size={12} /> 审批
                </Button>
              )}
            </div>
          )
        },
      },
    ],
    [role],
  )

  return (
    <>
      <PageHeader
        title="AI 任务中心"
        sub="护栏：BR-01 脱敏 · BR-02 审批 · BR-03 预算 · BR-10 审计 · BR-12 本地优先"
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-4">
        <StatCard label="本月调用" icon="term" value={stats.calls} sub={`任务数 ${tasks.length}`} />
        <StatCard
          label="token 消耗"
          icon="spark"
          value={formatNumber(stats.tokens)}
          sub={
            <>
              月度预算占比 {formatPercent(stats.tokenRatio)}{' '}
              <span className={stats.tokenRatio > 0.9 ? 'down' : 'up'}>· BR-03</span>
            </>
          }
        />
        <StatCard
          label="待审批"
          icon="clock"
          value={stats.pending}
          sub={<span className={stats.pending > 0 ? 'warm' : ''}>30min 超时自动取消（BR-02）</span>}
        />
        <StatCard
          label="本地模型占比"
          icon="shield"
          value={formatPercent(stats.localRatio)}
          sub="本地优先路由（BR-12）"
        />
      </div>

      <Card
        header="AI 任务"
        icon="spark"
        right={<span className="tiny text-dim num">共 {data?.total ?? 0} 条</span>}
      >
        <DataTable
          ariaLabel="AI 任务列表"
          columns={columns}
          data={tasks}
          rowClass={(row: Row<AITask>) =>
            row.original.status === 'pending_approval' ? 'hl' : undefined
          }
          emptyText="暂无 AI 任务"
        />
      </Card>

      {approving && (
        <ApprovalModal
          task={approving}
          onClose={() => setApproving(null)}
          onDecide={(id, ok) => (ok ? actions.approve.mutate(id) : actions.cancel.mutate(id))}
        />
      )}
      {callLogOf && <CallLogModal task={callLogOf} onClose={() => setCallLogOf(null)} />}
    </>
  )
}

function ApprovalModal({
  task,
  onClose,
  onDecide,
}: {
  task: AITask
  onClose: () => void
  onDecide: (id: number, approve: boolean) => void
}): JSX.Element {
  const tools = ['k8s_get_pods', 'k8s_get_events', 'k8s_describe_node']
  const callRatio = task.budget.max_calls > 0 ? task.calls_used / task.budget.max_calls : 0
  return (
    <Modal
      open
      onClose={onClose}
      label={`审批 AI 任务 #${task.id}`}
      title={
        <>
          <Icon name="spark" size={15} className="text-ai-text" /> 审批 AI 任务 · #{task.id}（
          {TYPE_LABELS[task.type]}）
        </>
      }
      footer={
        <>
          <Button variant="danger" onClick={() => onDecide(task.id, false)}>
            <Icon name="x" size={14} /> 拒绝
          </Button>
          <Button variant="primary" onClick={() => onDecide(task.id, true)}>
            <Icon name="check" size={14} /> 批准
          </Button>
        </>
      }
    >
      <div>
        <div className="tiny text-tx2 mb-1">将要执行的工具（默认只读，BR-02）</div>
        <CodeBlock
          text={tools.map((t) => `ai.tool.run --readonly ${t}`).join('\n')}
          ariaLabel="待执行工具清单"
        />
      </div>
      <Kv
        rows={[
          ['预算已消耗', <BudgetBar ratio={callRatio} />],
          ['calls', `${task.calls_used} / ${task.budget.max_calls}`],
          [
            'tokens',
            `${formatNumber(task.tokens_used)} / ${formatNumber(task.budget.max_output_tokens)}`,
          ],
          ['审批截止', task.approval_deadline_at ? formatDateTime(task.approval_deadline_at) : '—'],
        ]}
      />
      <p className="tiny text-dim flex items-start gap-1">
        <Icon name="clock" size={12} className="mt-0.5" />
        审批超时（默认 30
        分钟）视为拒绝，任务自动取消并通知发起人（BR-02）；本次决定计入审计（BR-10）。
      </p>
    </Modal>
  )
}

function CallLogModal({ task, onClose }: { task: AITask; onClose: () => void }): JSX.Element {
  const { data } = useCallLogs(task.id)
  const logs = data?.items ?? []
  return (
    <Modal
      open
      onClose={onClose}
      label={`调用链 #${task.id}`}
      width={680}
      title={
        <>
          <Icon name="term" size={15} className="text-tx2" /> 调用链审计 · 任务 #{task.id}
        </>
      }
      footer={
        <span className="tiny text-dim mr-auto">
          AICallLog 只追加不可删改（BR-10 / D-6）；prompt 仅存摘要不存明文（BR-01）
        </span>
      }
    >
      {logs.length === 0 ? (
        <Empty text="暂无调用记录" />
      ) : (
        <LinkList>
          {logs.map((l) => (
            <LinkItem key={l.id} icon="term" readOnly>
              <span className="mono">{l.model}</span>
              {l.tool_used && <span className="tag">{l.tool_used}</span>}
              <span className="tiny text-tx2 num ml-auto">
                in {formatNumber(l.tokens_in)} / out {formatNumber(l.tokens_out)} · {l.latency_ms}ms
              </span>
              <span className={`tiny ${l.result_code === 'ok' ? 'up' : 'down'}`}>
                {l.result_code}
              </span>
            </LinkItem>
          ))}
        </LinkList>
      )}
    </Modal>
  )
}
