/** 候选事件确认队列（P2，hifi §3.3）：候选卡（规则 + 成员告警 + 相似度）→ 确认立项 / 驳回三原因。
 *  BR-04：关联规则产生的候选事件必须人工确认后才正式立项；驳回原因回流规则调优。 */
import { useState, type JSX } from 'react'
import { useNavigate } from 'react-router'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, unwrap } from '../../../shared/api/client'
import { qk } from '../../../shared/lib/query-keys'
import type { IncidentCandidate } from '../../../shared/api/types'
import { PageHeader, Card, Empty, RuleBox, LinkItem, LinkList } from '../../../shared/ui/data'
import { Button } from '../../../shared/ui/button'
import { Modal } from '../../../shared/ui/overlays'
import { RadioCards, Label, Textarea } from '../../../shared/ui/inputs'
import { SevChip } from '../../../shared/ui/chips'
import { Icon } from '../../../shared/ui/icon'
import { toast } from '../../../shared/ui/toast'
import { formatRelative } from '../../../shared/lib/format'
import { can } from '../../../shared/types/permissions'
import { useRole } from '../../session'

const REJECT_REASONS = [
  { value: 'rule_too_broad', label: '规则过宽', description: '匹配条件过宽，命中了不该聚合的告警' },
  { value: 'time_window_too_long', label: '时间窗过长', description: '时间窗口超出合理聚合范围' },
  {
    value: 'enrichment_field_error',
    label: '富化字段错误',
    description: '用于关联的富化字段数据有误',
  },
]

function useCandidates() {
  return useQuery({
    queryKey: qk.candidates.list({ limit: 100 }),
    queryFn: async () => {
      const res = await api.GET('/incident-candidates', { params: { query: { limit: 100 } } })
      return unwrap(res)
    },
  })
}

function useDecide() {
  const qc = useQueryClient()
  const invalidate = () => {
    void qc.invalidateQueries({ predicate: (q) => q.queryKey[0] === 'candidates' })
    void qc.invalidateQueries({ predicate: (q) => q.queryKey[0] === 'incidents' })
    void qc.invalidateQueries({ predicate: (q) => q.queryKey[0] === 'nav-badge' })
  }
  const confirm = useMutation({
    mutationFn: async (id: number) => {
      const res = await api.POST('/incident-candidates/{id}/confirm', { params: { path: { id } } })
      return unwrap(res)
    },
    onSuccess: (incident) => {
      invalidate()
      const created = incident as { id: number }
      toast.show({
        title: '候选已确认立项',
        description: `事件 #${created.id} 已创建并关联成员告警（BR-04）`,
        variant: 'ok',
        action: {
          label: '前往事件',
          onClick: () => window.location.assign(`/incidents/${created.id}`),
        },
      })
    },
  })
  const reject = useMutation({
    mutationFn: async ({
      id,
      body,
    }: {
      id: number
      body: { reject_reason: string; note?: string }
    }) => {
      const res = await api.POST('/incident-candidates/{id}/reject', {
        params: { path: { id } },
        body: body as {
          reject_reason: 'rule_too_broad' | 'time_window_too_long' | 'enrichment_field_error'
          note?: string
        },
      })
      return unwrap<IncidentCandidate>(res)
    },
    onSuccess: () => {
      invalidate()
      toast.show({
        title: '候选已驳回',
        description: '驳回原因已回流规则调优（BR-04）',
        variant: 'ok',
      })
    },
  })
  return { confirm, reject }
}

function RejectModal({
  candidate,
  onClose,
}: {
  candidate: IncidentCandidate
  onClose: () => void
}): JSX.Element {
  const [reason, setReason] = useState('')
  const [note, setNote] = useState('')
  const { reject } = useDecide()
  return (
    <Modal
      open
      onClose={onClose}
      label="驳回候选事件"
      title={
        <>
          <Icon name="x" size={15} className="text-tx2" /> 驳回候选事件 · #{candidate.id}
        </>
      }
      footer={
        <>
          <Button onClick={onClose}>取消</Button>
          <Button
            variant="primary"
            disabled={!reason || reject.isPending}
            onClick={() =>
              reject.mutate(
                { id: candidate.id, body: { reject_reason: reason, note: note || undefined } },
                { onSuccess: onClose },
              )
            }
          >
            提交驳回
          </Button>
        </>
      }
    >
      <RadioCards
        name="reject-reason"
        value={reason}
        onChange={setReason}
        options={REJECT_REASONS}
        ariaLabel="驳回原因"
      />
      <div>
        <Label htmlFor="reject-note">补充说明（可选）</Label>
        <Textarea
          id="reject-note"
          rows={3}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
      </div>
      <p className="tiny text-dim">驳回原因将回流规则调优（BR-04），并计入审计（BR-10）。</p>
    </Modal>
  )
}

function CandidateCard({ candidate }: { candidate: IncidentCandidate }): JSX.Element {
  const { confirm } = useDecide()
  const [rejecting, setRejecting] = useState(false)
  const navigate = useNavigate()
  const role = useRole()
  const { data: ruleRes } = useQuery({
    queryKey: ['correlation-rule', candidate.correlation_rule_id],
    queryFn: async () => {
      const res = await api.GET('/correlation-rules/{id}', {
        params: { path: { id: candidate.correlation_rule_id } },
      })
      return unwrap(res)
    },
  })
  const { data: alertsRes } = useQuery({
    queryKey: ['candidate-members', candidate.member_alert_ids],
    queryFn: async () => {
      const res = await api.GET('/alerts', {
        params: { query: { limit: 200, fingerprint: '' } },
      })
      return unwrap(res)
    },
  })
  const members = (alertsRes?.items ?? []).filter((a) => candidate.member_alert_ids.includes(a.id))
  const decidable = can(role, 'candidate.decide') && candidate.status === 'pending'

  return (
    <Card>
      <div className="card-h">
        <Icon name="layers" size={13} />
        <span className="atitle">{candidate.title}</span>
        <span className="tag pu ml-auto">候选 · CAND-{candidate.id}</span>
      </div>
      <div className="card-b flex flex-col gap-3">
        <RuleBox
          ruleCode={`#${candidate.correlation_rule_id} ${ruleRes?.name ?? ''}`}
          description={ruleRes?.mode === 'auto' ? 'auto 模式' : 'candidate 模式（人工确认）'}
          window_={`${(ruleRes as { time_window_seconds?: number } | undefined)?.time_window_seconds ?? '-'}s`}
          similarity={candidate.similarity}
        />
        <div>
          <div className="tiny text-dim mb-1">成员告警（{members.length}）</div>
          <LinkList>
            {members.map((a) => (
              <LinkItem
                key={a.id}
                icon="siren"
                onClick={() => void navigate(`/alerts?selected=${a.id}`)}
              >
                <SevChip severity={a.severity} />
                <span className="atitle truncate flex-1">{a.title ?? a.fingerprint}</span>
                <span className="chip sev-p2 num">×{a.occurrence_count}</span>
                <span className="mono text-tx2 hidden md:block">{a.fingerprint}</span>
              </LinkItem>
            ))}
          </LinkList>
        </div>
        {candidate.status === 'pending' ? (
          <div className="flex items-center gap-2">
            <Button
              variant="primary"
              disabled={!decidable || confirm.isPending}
              onClick={() => confirm.mutate(candidate.id)}
            >
              <Icon name="check" size={14} /> 确认立项
            </Button>
            <Button disabled={!decidable} onClick={() => setRejecting(true)}>
              <Icon name="x" size={14} /> 驳回
            </Button>
            <div className="flex-1" />
            <span className="tiny text-dim">
              驳回原因回流规则调优 · {formatRelative(candidate.created_at)}
            </span>
          </div>
        ) : (
          <div className="tiny text-dim">
            {candidate.status === 'confirmed'
              ? '已确认立项'
              : `已驳回（${REJECT_REASONS.find((r) => r.value === candidate.reject_reason)?.label ?? candidate.reject_reason}）`}
          </div>
        )}
      </div>
      {rejecting && <RejectModal candidate={candidate} onClose={() => setRejecting(false)} />}
    </Card>
  )
}

export function CandidatesPage(): JSX.Element {
  const { data } = useCandidates()
  const pending = (data?.items ?? []).filter((c) => c.status === 'pending')
  const decided = (data?.items ?? []).filter((c) => c.status !== 'pending')

  return (
    <>
      <PageHeader
        title="候选事件确认队列"
        sub="关联规则 candidate 模式命中产生，确认后才正式立项（BR-04）"
      />
      <div className="flex flex-col gap-4">
        {pending.length === 0 && decided.length === 0 && (
          <Card>
            <Empty icon="layers" text="队列为空" sub="所有候选已确认或驳回" />
          </Card>
        )}
        {pending.map((c) => (
          <CandidateCard key={c.id} candidate={c} />
        ))}
        {decided.length > 0 && (
          <Card header="近期已处置" icon="check">
            <div className="card-b flex flex-col gap-2">
              {decided.map((c) => (
                <div key={c.id} className="tiny text-tx2 flex items-center gap-2">
                  <span className="tag">{c.status === 'confirmed' ? '已立项' : '已驳回'}</span>
                  {c.title}
                  <span className="ml-auto num">
                    {formatRelative(c.decided_at ?? c.created_at)}
                  </span>
                </div>
              ))}
            </div>
          </Card>
        )}
      </div>
    </>
  )
}
