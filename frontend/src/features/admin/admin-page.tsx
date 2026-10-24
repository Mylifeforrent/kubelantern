/** 管理后台（P0，hifi §3.10）：集群与凭证 / Provider 接入 / 巡检规则库 / AI 预算与模型路由 +
 *  用户与角色 + 审计日志。硬规则：凭证只展示 secret_ref 引用，永不回显凭证值。 */
import { useState, type JSX } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { PageHeader, Card, Empty, Kv, LinkItem, LinkList, StatCard } from '../../shared/ui/data'
import { Button } from '../../shared/ui/button'
import { Modal } from '../../shared/ui/overlays'
import { Input, Select, Label } from '../../shared/ui/inputs'
import { ClusterStatusChip } from '../../shared/ui/chips'
import { Icon } from '../../shared/ui/icon'
import { api, unwrap } from '../../shared/api/client'
import { qk } from '../../shared/lib/query-keys'
import { can } from '../../shared/types/permissions'
import { useRole } from '../session'
import { toast } from '../../shared/ui/toast'
import { formatDateTime, formatRelative } from '../../shared/lib/format'
import type { Cluster, User } from '../../shared/api/types'

export function AdminPage(): JSX.Element {
  const role = useRole()
  const editable = can(role, 'admin.config')
  const qc = useQueryClient()
  const { data: clusterData } = useQuery({
    queryKey: qk.admin.clusters(),
    queryFn: async () => {
      const res = await api.GET('/clusters', { params: { query: { limit: 100 } } })
      return unwrap(res)
    },
  })
  const { data: providerData } = useQuery({
    queryKey: qk.admin.providers(),
    queryFn: async () => {
      const res = await api.GET('/providers', { params: { query: { limit: 100 } } })
      return unwrap(res)
    },
  })
  const { data: ruleData } = useQuery({
    queryKey: qk.inspections.rules(),
    queryFn: async () => {
      const res = await api.GET('/inspection-rules', { params: { query: { limit: 200 } } })
      return unwrap(res)
    },
  })
  const { data: auditData } = useQuery({
    queryKey: qk.admin.auditLogs({ limit: 20 }),
    queryFn: async () => {
      const res = await api.GET('/audit-logs', { params: { query: { limit: 20 } } })
      return unwrap(res)
    },
  })
  const testConn = useMutation({
    mutationFn: async (id: number) => {
      const res = await api.POST('/clusters/{id}/test-connection', { params: { path: { id } } })
      return unwrap(res)
    },
    onSuccess: (r) => {
      void qc.invalidateQueries({ predicate: (q) => q.queryKey.includes('admin') })
      toast.show({ title: '探活完成', description: `状态：${r.status}`, variant: 'ok' })
    },
  })
  const [userOpen, setUserOpen] = useState(false)
  const clusters = clusterData?.items ?? []

  return (
    <>
      <PageHeader
        title="管理后台"
        sub="集群与凭证凭 secret_ref 引用接入；凭证值永不入库、永不回显（安全红线）"
        actions={editable ? undefined : <span className="tag gd">只读（admin 专属）</span>}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card
          header="集群与凭证"
          icon="radar"
          right={
            editable && (
              <Button
                small
                onClick={() => testConn.mutate(clusters[0]?.id ?? 0)}
                disabled={clusters.length === 0}
              >
                探活
              </Button>
            )
          }
        >
          <div className="card-b">
            {clusters.length === 0 ? (
              <Empty text="尚未接入集群" />
            ) : (
              <LinkList>
                {clusters.map((c: Cluster) => (
                  <LinkItem
                    key={c.id}
                    icon="shield"
                    readOnly
                    right={<ClusterStatusChip status={c.status} />}
                  >
                    <span className="atitle">{c.name}</span>
                    <span className="tiny text-tx2">
                      {c.environment} · {c.k8s_version ?? '版本未知'} · credential #
                      {c.credential_id}（secret_ref 引用）
                    </span>
                  </LinkItem>
                ))}
              </LinkList>
            )}
          </div>
        </Card>

        <Card header="Provider 接入" icon="link">
          <div className="card-b">
            {(providerData?.items ?? []).length === 0 ? (
              <Empty text="暂无告警源" />
            ) : (
              <LinkList>
                {(providerData?.items ?? []).map((p) => (
                  <LinkItem
                    key={p.id}
                    icon="link"
                    readOnly
                    right={<span className="tag">{p.pull_mode ?? p.category}</span>}
                  >
                    <span className="atitle">{p.name}</span>
                    <span className="tiny text-tx2">
                      {p.type} · {p.category} · fingerprint: {p.fingerprint_fields.join('/') || '—'}
                    </span>
                  </LinkItem>
                ))}
              </LinkList>
            )}
          </div>
        </Card>

        <Card header="巡检规则库" icon="file">
          <div className="card-b">
            <Kv
              rows={[
                ['规则总数', ruleData?.total ?? 0],
                ['启用中', (ruleData?.items ?? []).filter((r) => r.enabled).length],
                ['版本适配', 'k8s_version_fit 逐规则标注（规则库纳入 CI）'],
                ['更新来源', 'k8sgpt-migration / builtin / community'],
              ]}
            />
          </div>
        </Card>

        <Card header="AI 预算与模型路由" icon="spark">
          <div className="card-b">
            <Kv
              rows={[
                ['默认预算', '40 次调用 / 100k 输出 token（BR-03，管理员可调）'],
                ['模型路由', '本地优先（Ollama / vLLM，BR-12）'],
                [
                  '数据出域',
                  <span className="flex items-center gap-1">
                    默认「仅本地」<span className="tag gd">TBD-BIZ</span>
                  </span>,
                ],
                ['审计', 'AICallLog 只追加（BR-10 / D-6）'],
              ]}
            />
          </div>
        </Card>

        <Card
          header="用户与角色"
          icon="user"
          right={
            editable && (
              <Button small onClick={() => setUserOpen(true)}>
                <Icon name="plus" size={12} /> 创建用户
              </Button>
            )
          }
        >
          <div className="card-b">
            <UserTable />
          </div>
        </Card>

        <Card
          header="审计日志（只读）"
          icon="clock"
          right={<span className="tiny text-dim">BR-10 · 不可删改（D-6）</span>}
        >
          <div className="card-b">
            {(auditData?.items ?? []).length === 0 ? (
              <Empty text="暂无审计记录" />
            ) : (
              <div className="flex flex-col gap-2">
                {(auditData?.items ?? []).slice(0, 8).map((l) => (
                  <div key={l.id} className="tiny flex items-center gap-2">
                    <span className="tag">
                      {l.actor_type === 'system' ? 'system' : `#${l.actor_user_id ?? '-'}`}
                    </span>
                    <span className="mono">{l.action}</span>
                    <span className="text-tx2">
                      {l.resource_type}#{l.resource_id}
                    </span>
                    <span className="ml-auto text-dim num">{formatRelative(l.created_at)}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mt-4">
        <StatCard
          label="集群"
          icon="radar"
          value={clusters.length}
          sub={`探活正常 ${clusters.filter((c) => c.status === 'connected').length}`}
        />
        <StatCard
          label="告警源"
          icon="link"
          value={providerData?.total ?? 0}
          sub="source / query / action"
        />
        <StatCard
          label="巡检规则"
          icon="file"
          value={ruleData?.total ?? 0}
          sub="规则库纳入平台 CI"
        />
        <StatCard label="审计事件" icon="clock" value={auditData?.total ?? 0} sub="只追加（D-6）" />
      </div>

      {userOpen && <CreateUserModal onClose={() => setUserOpen(false)} />}
    </>
  )
}

function UserTable(): JSX.Element {
  const { data } = useQuery({
    queryKey: qk.admin.users({ limit: 100 }),
    queryFn: async () => {
      const res = await api.GET('/users', { params: { query: { limit: 100 } } })
      return unwrap(res)
    },
  })
  const users = data?.items ?? []
  if (users.length === 0) return <Empty text="暂无用户" />
  return (
    <LinkList>
      {users.map((u: User) => (
        <LinkItem
          key={u.id}
          icon="user"
          readOnly
          right={<span className="tag">{u.roles?.[0]?.role_code ?? '—'}</span>}
        >
          <span className="atitle">{u.display_name}</span>
          <span className="tiny text-tx2">
            {u.username} · {u.team} · {u.is_active ? '启用' : '停用'}
          </span>
        </LinkItem>
      ))}
    </LinkList>
  )
}

function CreateUserModal({ onClose }: { onClose: () => void }): JSX.Element {
  const qc = useQueryClient()
  const [username, setUsername] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [team, setTeam] = useState('platform')
  const [roleCode, setRoleCode] = useState('developer')
  const create = useMutation({
    mutationFn: async () => {
      const res = await api.POST('/users', {
        body: {
          username,
          email: `${username}@example.com`,
          display_name: displayName || username,
          team,
          roles: [{ role_code: roleCode as 'admin' }],
        },
      })
      return unwrap<User>(res)
    },
    onSuccess: (u) => {
      void qc.invalidateQueries({ predicate: (q) => q.queryKey[0] === 'users' })
      toast.show({
        title: `用户 ${u.username} 已创建`,
        description: '角色已授予；操作已留痕（BR-10）',
        variant: 'ok',
      })
      onClose()
    },
  })
  return (
    <Modal
      open
      onClose={onClose}
      label="创建用户"
      title={
        <>
          <Icon name="plus" size={15} className="text-tx2" /> 创建用户
        </>
      }
      footer={
        <>
          <Button onClick={onClose}>取消</Button>
          <Button
            variant="primary"
            disabled={!username || create.isPending}
            onClick={() => create.mutate()}
          >
            创建
          </Button>
        </>
      }
    >
      <div className="grid grid-cols-2 gap-3">
        <div>
          <Label htmlFor="nu-username">用户名</Label>
          <Input id="nu-username" value={username} onChange={(e) => setUsername(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="nu-display">显示名</Label>
          <Input
            id="nu-display"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor="nu-team">团队（developer 团队隔离依据）</Label>
          <Input id="nu-team" value={team} onChange={(e) => setTeam(e.target.value)} />
        </div>
        <div>
          <Label htmlFor="nu-role">角色</Label>
          <Select
            value={roleCode}
            onChange={setRoleCode}
            ariaLabel="角色选择"
            options={[
              { value: 'admin', label: '平台管理员' },
              { value: 'sre', label: 'SRE 工程师' },
              { value: 'oncall_manager', label: '值班经理' },
              { value: 'developer', label: '研发工程师' },
              { value: 'viewer', label: '访客' },
            ]}
          />
        </div>
      </div>
      <p className="tiny text-dim">
        developer 角色需带团队（T 限本团队行级过滤由后端执行）；创建时间{' '}
        {formatDateTime(new Date().toISOString())}。
      </p>
    </Modal>
  )
}
