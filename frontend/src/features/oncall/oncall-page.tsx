/** 排班与升级（P2，hifi §3.9）：周历（7 列 grid 自实现 [ASSUMPTION]）+ 轮换/顶班 + 升级策略表。
 *  编辑权 admin/oncall_manager（领域 §3）；sre 只读 [ASSUMPTION]（前端 §3.1）。 */
import { useState, type JSX } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { PageHeader, Card, Empty, Kv } from '../../shared/ui/data'
import { Button } from '../../shared/ui/button'
import { OkChip } from '../../shared/ui/chips'
import { Icon } from '../../shared/ui/icon'
import { Input, Label } from '../../shared/ui/inputs'
import { Modal } from '../../shared/ui/overlays'
import { api, unwrap } from '../../shared/api/client'
import { qk } from '../../shared/lib/query-keys'
import { can } from '../../shared/types/permissions'
import { useRole } from '../session'
import { toast } from '../../shared/ui/toast'
import { formatDateTime } from '../../shared/lib/format'
import type { OnCallSchedule } from '../../shared/api/types'

const WEEKDAYS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']

function useSchedule() {
  return useQuery({
    queryKey: qk.oncall.schedules(),
    queryFn: async () => {
      const res = await api.GET('/oncall-schedules', { params: { query: { limit: 20 } } })
      return unwrap(res)
    },
  })
}

function useEscalations() {
  return useQuery({
    queryKey: qk.oncall.escalationPolicies(),
    queryFn: async () => {
      const res = await api.GET('/escalation-policies', { params: { query: { limit: 20 } } })
      return unwrap(res)
    },
  })
}

function useUpdateSchedule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, body }: { id: number; body: Record<string, unknown> }) => {
      const res = await api.PUT('/oncall-schedules/{id}', {
        params: { path: { id } },
        body: body as Record<string, never>,
      })
      return unwrap(res)
    },
    onSuccess: () => {
      void qc.invalidateQueries({ predicate: (q) => q.queryKey[0] === 'oncall-schedules' })
      toast.show({
        title: '排班已更新',
        description: '变更即时生效并计入审计（BR-10）',
        variant: 'ok',
      })
    },
  })
}

export function OncallPage(): JSX.Element {
  const role = useRole()
  const editable = can(role, 'oncall.edit')
  const { data: scheduleData } = useSchedule()
  const { data: escalationData } = useEscalations()
  const schedule = scheduleData?.items[0]
  const escalation = escalationData?.items[0]
  const update = useUpdateSchedule()
  const [overrideOpen, setOverrideOpen] = useState(false)

  const days =
    (
      schedule?.calendar as
        { days?: { date: number; primary: string; backup: string }[] } | undefined
    )?.days ?? []
  const todayIdx = (new Date().getDay() + 6) % 7

  return (
    <>
      <PageHeader
        title="排班与升级"
        sub="升级链每级超时未确认自动升级下一级；每一次投递与响应都有留痕（BR-08）"
        actions={
          editable ? (
            <OkChip label="可编辑" />
          ) : (
            <span className="tag gd">只读（排班/升级管理为 admin / 值班经理）</span>
          )
        }
      />

      <div className="flex flex-col gap-4">
        <Card
          header={`本周排班 · ${schedule?.name ?? '—'}`}
          icon="cal"
          right={
            editable && (
              <Button small onClick={() => setOverrideOpen(true)}>
                <Icon name="plus" size={12} /> 临时顶班
              </Button>
            )
          }
        >
          <div className="card-b">
            {days.length === 0 ? (
              <Empty text="暂无排班数据" />
            ) : (
              <div className="week">
                {days.map((d, i) => (
                  <div key={i} className={i === todayIdx ? 'day today' : 'day'}>
                    <div className="dw">{WEEKDAYS[i] ?? ''}</div>
                    <div className="pm">
                      {d.primary}
                      <small>主班</small>
                    </div>
                    <div className="bk">
                      {d.backup}
                      <small>备班</small>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <Card header="轮换规则" icon="refresh">
            <div className="card-b">
              {schedule ? (
                <Kv
                  rows={[
                    [
                      '成员',
                      (schedule.rotation_rules as { members?: string[] }).members?.join(' → ') ??
                        '—',
                    ],
                    [
                      '轮换周期',
                      `${(schedule.rotation_rules as { period_days?: number }).period_days ?? '-'} 天`,
                    ],
                    ['临时顶班', `${schedule.overrides.length} 条记录`],
                    ['状态', schedule.enabled ? '启用' : '停用'],
                  ]}
                />
              ) : (
                <Empty text="暂无排班表" />
              )}
            </div>
          </Card>

          <Card header="升级策略" icon="bell">
            <div className="card-b">
              {escalation ? (
                <>
                  <div className="overflow-x-auto">
                    <table className="tbl" aria-label="升级策略级别">
                      <thead>
                        <tr>
                          <th>级别</th>
                          <th>目标与渠道</th>
                          <th>超时</th>
                        </tr>
                      </thead>
                      <tbody>
                        {escalation.levels.map((l) => (
                          <tr key={l.level}>
                            <td className="num">L{l.level}</td>
                            <td>
                              {l.target} · {l.channel}
                            </td>
                            <td className="num">{l.timeout_min} min</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="tiny text-dim mt-2">
                    渠道降级链：IM → 短信 → 电话（BR-13）；各级默认超时与渠道组合
                    [TBD-BIZ]（业务负责人 / P2 设计前）。
                  </p>
                </>
              ) : (
                <Empty text="暂无升级策略" />
              )}
            </div>
          </Card>
        </div>
      </div>

      {overrideOpen && schedule && (
        <OverrideModal
          schedule={schedule}
          onClose={() => setOverrideOpen(false)}
          onSubmit={(member, backup, reason) =>
            update.mutate(
              {
                id: schedule.id,
                body: {
                  overrides: [
                    ...schedule.overrides,
                    {
                      id: Date.now(),
                      member,
                      backup,
                      reason,
                      from: new Date().toISOString(),
                      to: new Date(Date.now() + 86_400_000).toISOString(),
                    },
                  ],
                },
              },
              { onSuccess: () => setOverrideOpen(false) },
            )
          }
        />
      )}
    </>
  )
}

function OverrideModal({
  schedule,
  onClose,
  onSubmit,
}: {
  schedule: OnCallSchedule
  onClose: () => void
  onSubmit: (member: string, backup: string, reason: string) => void
}): JSX.Element {
  const [member, setMember] = useState('')
  const [backup, setBackup] = useState('')
  const [reason, setReason] = useState('')
  const members = (schedule.rotation_rules as { members?: string[] }).members ?? []
  return (
    <Modal
      open
      onClose={onClose}
      label="临时顶班"
      title={
        <>
          <Icon name="user" size={15} className="text-tx2" /> 临时顶班（L2）
        </>
      }
      footer={
        <>
          <Button onClick={onClose}>取消</Button>
          <Button
            variant="primary"
            disabled={!member || !backup}
            onClick={() => onSubmit(member, backup, reason)}
          >
            提交
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label htmlFor="ov-member">顶班人</Label>
          <Input
            id="ov-member"
            value={member}
            onChange={(e) => setMember(e.target.value)}
            placeholder={members.join(' / ')}
          />
        </div>
        <div>
          <Label htmlFor="ov-backup">被顶替成员</Label>
          <Input
            id="ov-backup"
            value={backup}
            onChange={(e) => setBackup(e.target.value)}
            placeholder={members.join(' / ')}
          />
        </div>
      </div>
      <div>
        <Label htmlFor="ov-reason">事由（休假 / 出差等）</Label>
        <Input id="ov-reason" value={reason} onChange={(e) => setReason(e.target.value)} />
      </div>
      <p className="tiny text-dim">
        已有顶班记录：{schedule.overrides.length} 条；最近一条{' '}
        {formatDateTime(
          String(
            (schedule.overrides[0] as { from?: string } | undefined)?.from ?? schedule.updated_at,
          ),
        )}
        。
      </p>
    </Modal>
  )
}
