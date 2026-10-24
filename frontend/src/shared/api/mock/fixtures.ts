/** mock fixtures（中文语境 + 边界值 + 空态/异常态数据，05-fe-be-boundary §3.2）。
 *  所有字段名/枚举值严格来自 docs/04-api/openapi.yaml（schema enum 同源）。 */
import type {
  AICallLog,
  AITask,
  Alert,
  AuditLog,
  Finding,
  Incident,
  NotificationRecord,
  RoleCode,
} from '../types'
import { db, isoAgo, nextId, type MockUser } from './state'

function user(
  id: number,
  username: string,
  displayName: string,
  team: string,
  role: RoleCode,
): MockUser {
  return {
    id,
    username,
    email: `${username}@example.com`,
    display_name: displayName,
    team,
    roles: [{ role_code: role }],
    is_active: true,
    created_at: isoAgo(60 * 24 * 90),
    updated_at: isoAgo(60),
    // mock 专用（契约 User 无此类字段，真实认证 [TBD-INFRA]）
    pass: username,
  }
}

export function seed(): void {
  db.users = [
    user(1, 'admin', '运维负责人', 'platform', 'admin'),
    user(2, 'sre', '值班 SRE', 'platform', 'sre'),
    user(3, 'ocm', '值班经理', 'platform', 'oncall_manager'),
    user(4, 'dev', '支付研发', 'pay', 'developer'),
    user(5, 'view', '访客', '-', 'viewer'),
  ]
  db.roles = [
    {
      id: 1,
      code: 'admin',
      name: '平台管理员',
      permissions: {
        alerts: 'Y',
        incidents: 'Y',
        inspections: 'Y',
        oncall: 'Y',
        ai: 'Y',
        workflow: 'Y',
        admin: 'Y',
      },
      created_at: isoAgo(60 * 24 * 120),
      updated_at: isoAgo(60 * 24),
    },
    {
      id: 2,
      code: 'sre',
      name: 'SRE 工程师',
      permissions: {
        alerts: 'Y',
        incidents: 'Y',
        inspections: 'Y',
        oncall: 'N',
        ai: 'T',
        workflow: 'Y',
        admin: 'N',
      },
      created_at: isoAgo(60 * 24 * 120),
      updated_at: isoAgo(60 * 24),
    },
    {
      id: 3,
      code: 'oncall_manager',
      name: '值班经理',
      permissions: {
        alerts: 'R',
        incidents: 'R',
        inspections: 'N',
        oncall: 'Y',
        ai: 'N',
        workflow: 'N',
        admin: 'N',
      },
      created_at: isoAgo(60 * 24 * 120),
      updated_at: isoAgo(60 * 24),
    },
    {
      id: 4,
      code: 'developer',
      name: '研发工程师',
      permissions: {
        alerts: 'T',
        incidents: 'T',
        inspections: 'T',
        oncall: 'N',
        ai: 'N',
        workflow: 'N',
        admin: 'N',
      },
      created_at: isoAgo(60 * 24 * 120),
      updated_at: isoAgo(60 * 24),
    },
    {
      id: 5,
      code: 'viewer',
      name: '访客',
      permissions: {
        alerts: 'N',
        incidents: 'N',
        inspections: 'N',
        oncall: 'N',
        ai: 'N',
        workflow: 'N',
        admin: 'N',
      },
      created_at: isoAgo(60 * 24 * 120),
      updated_at: isoAgo(60 * 24),
    },
  ]

  db.clusters = [
    {
      id: 11,
      name: 'prod-cn-east-1',
      environment: 'prod',
      api_endpoint: 'https://prod-cn-east-1.example.com',
      status: 'connected',
      k8s_version: 'v1.29.4',
      credential_id: 101,
      last_checked_at: isoAgo(3),
      created_at: isoAgo(60 * 24 * 120),
      updated_at: isoAgo(60 * 24),
    },
    {
      id: 12,
      name: 'staging-cn-north-1',
      environment: 'staging',
      api_endpoint: 'https://staging-cn-north-1.example.com',
      status: 'degraded',
      k8s_version: 'v1.28.9',
      credential_id: 102,
      last_checked_at: isoAgo(9),
      created_at: isoAgo(60 * 24 * 90),
      updated_at: isoAgo(60 * 24),
    },
    {
      id: 13,
      name: 'dev-sandbox',
      environment: 'dev',
      api_endpoint: 'https://dev-sandbox.example.com',
      status: 'disconnected',
      credential_id: 103,
      last_checked_at: isoAgo(48),
      created_at: isoAgo(60 * 24 * 60),
      updated_at: isoAgo(60 * 24 * 2),
    },
  ]

  db.providers = [
    {
      id: 21,
      name: 'alertmanager-main',
      type: 'alertmanager',
      category: 'source',
      pull_mode: 'push',
      config: { endpoint: '/webhook/alertmanager' },
      fingerprint_fields: ['alertname', 'namespace', 'instance'],
      enabled: true,
      created_at: isoAgo(60 * 24 * 100),
      updated_at: isoAgo(60 * 24),
    },
    {
      id: 22,
      name: 'prometheus-query',
      type: 'prometheus',
      category: 'query',
      pull_mode: 'poll',
      config: { endpoint: 'http://prometheus.example.com' },
      fingerprint_fields: [],
      enabled: true,
      created_at: isoAgo(60 * 24 * 100),
      updated_at: isoAgo(60 * 24),
    },
    {
      id: 23,
      name: 'dingtalk-notify',
      type: 'dingtalk-action',
      category: 'action',
      config: { robot: 'sre-alerts' },
      fingerprint_fields: [],
      enabled: true,
      created_at: isoAgo(60 * 24 * 100),
      updated_at: isoAgo(60 * 24),
    },
  ]

  db.enrichmentRules = [
    {
      id: 31,
      name: '团队归属（namespace → team）',
      matchers: { namespace: '*' },
      mappings: [{ type: 'mapping', source: 'namespace', target: 'team' }],
      priority: 10,
      enabled: true,
      created_at: isoAgo(60 * 24 * 80),
      updated_at: isoAgo(60 * 24),
    },
    {
      id: 32,
      name: 'runbook 链接（alertname → 链接）',
      matchers: { alertname: 'PodCrashLooping' },
      mappings: [{ type: 'extraction', source: 'const', target: 'runbook' }],
      priority: 20,
      enabled: true,
      created_at: isoAgo(60 * 24 * 80),
      updated_at: isoAgo(60 * 24),
    },
  ]

  db.correlationRules = [
    {
      id: 41,
      name: '支付网关超时风暴',
      mode: 'candidate',
      conditions: {
        all: [
          { field: 'alertname', eq: 'GatewayTimeout' },
          { field: 'team', eq: 'pay' },
        ],
      },
      time_window_seconds: 300,
      confirm_count: 3,
      reject_count: 1,
      enabled: true,
      created_at: isoAgo(60 * 24 * 30),
      updated_at: isoAgo(60 * 24),
    },
    {
      id: 42,
      name: '节点资源连锁告警',
      mode: 'candidate',
      conditions: {
        any: [
          { field: 'alertname', eq: 'NodeMemoryHigh' },
          { field: 'alertname', eq: 'NodeDiskPressure' },
        ],
      },
      time_window_seconds: 600,
      confirm_count: 1,
      reject_count: 0,
      enabled: true,
      created_at: isoAgo(60 * 24 * 30),
      updated_at: isoAgo(60 * 24),
    },
  ]

  db.maintenanceWindows = [
    {
      id: 51,
      name: '支付库月度变更窗口',
      scope: { namespace: 'pay-db' },
      starts_at: isoAgo(120),
      ends_at: isoAgo(-240),
      reason: '版本发布，预期告警',
      created_by: 1,
      created_at: isoAgo(180),
    },
  ]

  // ---- 告警（覆盖状态机 8 态中的典型形态 + 合并计数 + 抑制 + 团队隔离） ----
  db.alerts = [
    alert(201, 'GatewayTimeout', 'critical', 'notified', 'pay', 47, '支付网关大量 504', 6, {
      service: 'pay-gateway',
      namespace: 'pay',
      runbook: 'https://wiki.example.com/runbook/gw-timeout',
    }),
    alert(
      202,
      'PodCrashLooping',
      'critical',
      'correlated',
      'platform',
      12,
      'checkout Pod 反复重启',
      22,
      { service: 'checkout', namespace: 'pay' },
    ),
    alert(
      203,
      'NodeMemoryHigh',
      'warning',
      'notified',
      'platform',
      3,
      'prod 节点内存水位 >90%',
      40,
      { namespace: 'platform', node: 'node-07' },
    ),
    alert(204, 'NodeDiskPressure', 'warning', 'correlated', 'platform', 5, 'node-07 磁盘压力', 65, {
      namespace: 'platform',
      node: 'node-07',
    }),
    alert(
      205,
      'CertExpirySoon',
      'info',
      'notified',
      'platform',
      1,
      'ingress 证书 14 天内到期',
      300,
      { namespace: 'ingress' },
    ),
    alert(
      206,
      'DeployJobFailed',
      'warning',
      'suppressed',
      'pay',
      2,
      '发布任务失败（维护窗口内）',
      30,
      { namespace: 'pay-db' },
      51,
    ),
    alert(
      207,
      'GatewayTimeout',
      'critical',
      'resolved',
      'pay',
      88,
      '支付网关大量 504（昨夜风暴，已恢复）',
      60 * 20,
      { service: 'pay-gateway', namespace: 'pay' },
    ),
    alert(208, 'HPAMaxedOut', 'warning', 'deduplicated', 'pay', 4, 'checkout HPA 已达上限', 12, {
      service: 'checkout',
      namespace: 'pay',
    }),
    alert(209, 'LatencyP99High', 'warning', 'notified', 'pay', 9, '结算接口 P99 > 2s', 18, {
      service: 'settle',
      namespace: 'pay',
    }),
    alert(210, 'Watchdog', 'info', 'notified', 'platform', 999, '心跳告警（持续触发）', 120, {
      namespace: 'platform',
    }),
  ]

  db.explanations = [
    {
      id: 301,
      finding_id: 631,
      task_id: 401,
      sanitized_input_digest: 'a3f1…c9d2',
      output: {
        summary: 'kube-proxy Pod 反复重启，事件显示 OOMKilled（limit 256Mi 过小）。',
        suggestions: [
          '将 memory limit 提升至 512Mi 并观察 24h',
          '核对 node-07 内存水位是否由其他负载挤占',
        ],
      },
      model: 'qwen2.5-7b-instruct（本地）',
      tokens: 1832,
      created_at: isoAgo(35),
    },
    {
      id: 302,
      finding_id: 636,
      task_id: 402,
      sanitized_input_digest: '77b0…12ae',
      output: {
        summary: 'staging 命名空间存在两个已失效的 ImagePullBackOff 负载，引用镜像 tag 已被覆盖。',
        suggestions: ['回滚到最近可用 tag', '为 CI 镜像 tag 添加不可变策略'],
      },
      model: 'qwen2.5-7b-instruct（本地）',
      tokens: 1420,
      created_at: isoAgo(90),
    },
  ]

  // ---- 候选事件（BR-04，pending 待确认） ----
  db.candidates = [
    {
      id: 701,
      correlation_rule_id: 42,
      title: 'node-07 资源连锁告警（内存 + 磁盘）',
      member_alert_ids: [203, 204],
      similarity: 0.87,
      status: 'pending',
      created_at: isoAgo(14),
    },
    {
      id: 702,
      correlation_rule_id: 41,
      title: '支付网关超时风暴（与 202 关联）',
      member_alert_ids: [201, 202],
      similarity: 0.72,
      status: 'pending',
      created_at: isoAgo(52),
    },
    {
      id: 703,
      correlation_rule_id: 41,
      title: '结算接口慢查询聚合',
      member_alert_ids: [209],
      similarity: 0.41,
      status: 'rejected',
      reject_reason: 'rule_too_broad',
      decided_by: 2,
      decided_at: isoAgo(240),
      created_at: isoAgo(300),
    },
  ]

  // ---- 事件（状态机 6 态覆盖） ----
  db.incidents = [
    incident(
      801,
      '支付网关 504 风暴（pay-gateway）',
      'P1',
      'acknowledged',
      'correlation',
      'pay',
      true,
      210,
      95,
    ),
    incident(
      802,
      'node-07 资源连锁（内存/磁盘）',
      'P2',
      'open',
      'correlation',
      'platform',
      false,
      65,
      60,
    ),
    incident(803, '结算接口 P99 劣化', 'P3', 'mitigated', 'manual', 'pay', false, 60 * 26, 60 * 20),
    incident(
      804,
      'ingress 证书更换',
      'P4',
      'closed',
      'manual',
      'platform',
      true,
      60 * 24 * 6,
      60 * 24 * 5,
    ),
    incident(
      805,
      '昨日发布失败误报',
      'P3',
      'cancelled',
      'manual',
      'pay',
      false,
      60 * 24 * 3,
      60 * 24 * 3,
    ),
  ]
  db.timelines = {
    801: [
      {
        occurred_at: isoAgo(210),
        kind: 'status_changed',
        summary: '事件立项（关联规则 #41 命中，成员告警 2 条）',
      },
      {
        occurred_at: isoAgo(190),
        kind: 'notification',
        summary: '一级升级链投递：IM → 值班 SRE（已 Ack）',
      },
      {
        occurred_at: isoAgo(95),
        kind: 'manual_note',
        summary: '初步定位：上游依赖连接池耗尽，已扩容连接数',
        actor_id: 2,
      },
      {
        occurred_at: isoAgo(94),
        kind: 'status_changed',
        summary: '值班人确认处理（acknowledged）',
        actor_id: 2,
      },
    ],
    802: [
      {
        occurred_at: isoAgo(65),
        kind: 'status_changed',
        summary: '候选事件 #701 确认立项（BR-04）',
        actor_id: 2,
      },
    ],
    803: [
      { occurred_at: isoAgo(60 * 26), kind: 'status_changed', summary: '人工立项' },
      {
        occurred_at: isoAgo(60 * 20),
        kind: 'status_changed',
        summary: '止血完成：临时限流已生效',
        actor_id: 1,
      },
    ],
    804: [
      { occurred_at: isoAgo(60 * 24 * 6), kind: 'status_changed', summary: '人工立项' },
      { occurred_at: isoAgo(60 * 24 * 5), kind: 'status_changed', summary: '事件关闭' },
    ],
    805: [
      {
        occurred_at: isoAgo(60 * 24 * 3),
        kind: 'status_changed',
        summary: '误报关闭（原因：变更窗口内预期告警）',
      },
    ],
  }
  db.postmortems = {
    804: {
      id: 901,
      incident_id: 804,
      timeline: [{ summary: '自动汇总自事件时间线（2 条）' }],
      root_cause: '证书轮换任务未纳入发布检查单',
      action_items: [
        {
          id: 1,
          content: '把证书轮换纳入巡检规则库',
          owner_id: 2,
          due_date: '2026-10-31',
          status: 'pending',
          created_at: isoAgo(60 * 24 * 5),
          updated_at: isoAgo(60 * 24 * 5),
        },
        {
          id: 2,
          content: '证书到期告警阈值 14→30 天',
          owner_id: 1,
          due_date: '2026-11-07',
          status: 'done',
          created_at: isoAgo(60 * 24 * 5),
          updated_at: isoAgo(60 * 24 * 4),
        },
      ],
      created_by: 1,
      created_at: isoAgo(60 * 24 * 5),
      updated_at: isoAgo(60 * 24 * 4),
    },
  }

  // ---- 巡检 ----
  db.inspectionRules = [
    {
      id: 601,
      code: 'POD_OOMKILLED',
      name: 'Pod OOMKilled 检测',
      category: 'workload',
      severity_default: 'warning',
      k8s_version_fit: '>=1.24',
      description: '来源：k8sgpt-migration',
      enabled: true,
      created_at: isoAgo(60 * 24 * 60),
      updated_at: isoAgo(60 * 24),
    },
    {
      id: 602,
      code: 'IMAGE_PULL_BACKOFF',
      name: '镜像拉取失败',
      category: 'workload',
      severity_default: 'warning',
      k8s_version_fit: '>=1.20',
      description: '来源：builtin',
      enabled: true,
      created_at: isoAgo(60 * 24 * 60),
      updated_at: isoAgo(60 * 24),
    },
    {
      id: 603,
      code: 'PVC_PENDING',
      name: 'PVC Pending 检测',
      category: 'storage',
      severity_default: 'critical',
      k8s_version_fit: '>=1.20',
      description: '来源：builtin',
      enabled: true,
      created_at: isoAgo(60 * 24 * 60),
      updated_at: isoAgo(60 * 24),
    },
    {
      id: 604,
      code: 'ENDPOINT_EMPTY',
      name: 'Service 无 Endpoints',
      category: 'network',
      severity_default: 'warning',
      k8s_version_fit: '>=1.20',
      description: '来源：community',
      enabled: false,
      created_at: isoAgo(60 * 24 * 60),
      updated_at: isoAgo(60 * 24),
    },
  ]
  db.policies = [
    {
      id: 611,
      cluster_id: 11,
      name: 'prod 全量巡检',
      schedule: '0 */2 * * *',
      ai_explain_level: 'warning',
      rule_ids: [601, 602, 603],
      enabled: true,
      created_at: isoAgo(60 * 24 * 50),
      updated_at: isoAgo(60 * 24),
    },
    {
      id: 612,
      cluster_id: 12,
      name: 'staging 每日巡检',
      schedule: '0 9 * * *',
      ai_explain_level: 'off',
      rule_ids: [601, 602],
      enabled: true,
      created_at: isoAgo(60 * 24 * 50),
      updated_at: isoAgo(60 * 24),
    },
  ]
  db.runs = [
    {
      id: 621,
      policy_id: 611,
      cluster_id: 11,
      trigger: 'schedule',
      status: 'succeeded',
      findings_count: 4,
      started_at: isoAgo(38),
      finished_at: isoAgo(36),
    },
    {
      id: 622,
      policy_id: 611,
      cluster_id: 11,
      trigger: 'manual',
      status: 'succeeded',
      findings_count: 5,
      started_at: isoAgo(60 * 5),
      finished_at: isoAgo(60 * 4.8),
    },
    {
      id: 623,
      policy_id: 612,
      cluster_id: 12,
      trigger: 'schedule',
      status: 'succeeded',
      findings_count: 2,
      started_at: isoAgo(60 * 12),
      finished_at: isoAgo(60 * 11.9),
    },
    {
      id: 624,
      policy_id: 612,
      cluster_id: 12,
      trigger: 'schedule',
      status: 'failed',
      findings_count: 0,
      error: '集群连接失败（探活 disconnected）',
      started_at: isoAgo(60 * 36),
      finished_at: isoAgo(60 * 36),
    },
  ]
  db.findings = [
    finding(
      631,
      621,
      11,
      'POD_OOMKILLED',
      'Pod',
      'kube-system',
      'kube-proxy-7x9kf',
      'warning',
      'open',
      { reason: 'OOMKilled', restarts: 7, message: 'memory limit 256Mi 过小' },
    ),
    finding(
      632,
      621,
      11,
      'PVC_PENDING',
      'PVC',
      'data',
      'clickhouse-data-2',
      'critical',
      'acknowledged',
      { message: '等待 storageclass provisioner', storage_class: 'ceph-rbd' },
    ),
    finding(
      633,
      621,
      11,
      'IMAGE_PULL_BACKOFF',
      'Pod',
      'staging-tools',
      'legacy-migrator',
      'warning',
      'open',
      { image: 'registry.example.com/legacy:20241001', message: 'manifest unknown' },
    ),
    finding(634, 621, 11, 'POD_OOMKILLED', 'Pod', 'pay', 'settle-worker-0', 'info', 'resolved', {
      reason: 'OOMKilled',
      restarts: 2,
    }),
    finding(
      635,
      622,
      11,
      'IMAGE_PULL_BACKOFF',
      'Pod',
      'platform',
      'grafana-sidecar',
      'warning',
      'ignored',
      { image: 'registry.example.com/grafana:dev', message: 'dev tag 已清理' },
      '开发联调镜像，忽略',
    ),
    finding(
      636,
      623,
      12,
      'ENDPOINT_EMPTY',
      'Service',
      'staging',
      'reporting-api',
      'warning',
      'open',
      { selector: 'app=reporting', message: '无匹配 Pod' },
    ),
    finding(637, 623, 12, 'POD_OOMKILLED', 'Pod', 'staging', 'mock-gen-1', 'info', 'open', {
      reason: 'OOMKilled',
    }),
  ]

  // ---- AI 任务与调用链（BR-02/03/05/10） ----
  db.aiTasks = [
    aiTask({
      id: 401,
      type: 'explain',
      status: 'completed',
      findingId: 631,
      callsUsed: 40,
      tokensUsed: 96_000,
      maxCalls: 40,
      maxTokens: 120_000,
      createdAt: isoAgo(36),
      finishedAt: isoAgo(35),
    }),
    aiTask({
      id: 402,
      type: 'explain',
      status: 'completed',
      findingId: 636,
      callsUsed: 40,
      tokensUsed: 88_000,
      maxCalls: 40,
      maxTokens: 120_000,
      createdAt: isoAgo(92),
      finishedAt: isoAgo(90),
    }),
    aiTask({
      id: 403,
      type: 'investigate',
      status: 'pending_approval',
      incidentId: 801,
      callsUsed: 25,
      tokensUsed: 18_400,
      maxCalls: 40,
      maxTokens: 100_000,
      requiresApproval: true,
      createdAt: isoAgo(8),
      approvalDeadline: isoAgo(-22),
    }),
    aiTask({
      id: 404,
      type: 'workflow_gen',
      status: 'pending_approval',
      incidentId: 802,
      callsUsed: 12,
      tokensUsed: 31_200,
      maxCalls: 40,
      maxTokens: 100_000,
      requiresApproval: true,
      createdAt: isoAgo(3),
      approvalDeadline: isoAgo(-27),
    }),
    aiTask({
      id: 405,
      type: 'explain',
      status: 'running',
      findingId: 633,
      callsUsed: 40,
      tokensUsed: 120_000,
      maxCalls: 40,
      maxTokens: 120_000,
      createdAt: isoAgo(2),
    }),
    aiTask({
      id: 406,
      type: 'investigate',
      status: 'budget_exceeded',
      incidentId: 803,
      callsUsed: 40,
      tokensUsed: 100_000,
      maxCalls: 40,
      maxTokens: 100_000,
      createdAt: isoAgo(60 * 20),
      finishedAt: isoAgo(60 * 19),
    }),
    aiTask({
      id: 407,
      type: 'explain',
      status: 'failed',
      findingId: 637,
      callsUsed: 40,
      tokensUsed: 3_400,
      maxCalls: 40,
      maxTokens: 120_000,
      createdAt: isoAgo(60 * 30),
      finishedAt: isoAgo(60 * 30),
      error: '模型端点超时（NoAI 熔断窗口内）',
    }),
  ]
  db.callLogs = [
    callLog(1, 403, 'qwen2.5-7b-instruct', 'k8s_get_pods', 'e2b0…41c7', 3200, 410, 1830, 'ok'),
    callLog(2, 403, 'qwen2.5-7b-instruct', 'k8s_get_events', '91af…07d3', 2800, 385, 1220, 'ok'),
    callLog(
      3,
      403,
      'qwen2.5-7b-instruct',
      'k8s_describe_node',
      '5c22…9b1e',
      4100,
      502,
      2310,
      'timeout',
      undefined,
      '上游 30s 超时',
    ),
    callLog(4, 401, 'qwen2.5-7b-instruct', undefined, 'd0fe…8812', 5100, 640, 2040, 'ok'),
    callLog(5, 402, 'qwen2.5-7b-instruct', undefined, '77aa…10bc', 4800, 590, 1980, 'ok'),
    callLog(6, 406, 'qwen2.5-14b-instruct', 'k8s_get_pods', 'aa01…77ce', 3600, 420, 1560, 'ok'),
    callLog(
      7,
      406,
      'qwen2.5-14b-instruct',
      'k8s_get_events',
      'bb02…88df',
      3900,
      460,
      1710,
      'error',
      undefined,
      '预算余量不足，任务终止',
    ),
  ]

  // ---- 值班（P2） ----
  db.schedules = [
    {
      id: 951,
      name: 'platform 值班表',
      team: 'platform',
      rotation_rules: { members: ['sre', 'admin', 'ocm'], period_days: 7, order: 'weekly' },
      calendar: {
        // 以本周一为起点，7 天主/备班
        start: isoAgo(60 * 24 * new Date().getDay() || 0),
        days: [
          { date: 0, primary: 'sre', backup: 'admin' },
          { date: 1, primary: 'sre', backup: 'admin' },
          { date: 2, primary: 'sre', backup: 'admin' },
          { date: 3, primary: 'admin', backup: 'ocm' },
          { date: 4, primary: 'admin', backup: 'ocm' },
          { date: 5, primary: 'admin', backup: 'ocm' },
          { date: 6, primary: 'ocm', backup: 'sre' },
        ],
      },
      overrides: [
        {
          id: 1,
          member: 'sre',
          from: isoAgo(-60 * 48),
          to: isoAgo(-60 * 24),
          backup: 'admin',
          reason: '休假（OOO）',
        },
      ],
      enabled: true,
      created_at: isoAgo(60 * 24 * 40),
      updated_at: isoAgo(60 * 24 * 2),
    },
  ]
  db.escalations = [
    {
      id: 961,
      name: 'P1/P2 默认升级链',
      schedule_id: 951,
      levels: [
        { level: 1, target: '当班主班', channel: 'IM', timeout_min: 10 },
        { level: 2, target: '当班备班', channel: 'IM', timeout_min: 10 },
        { level: 3, target: 'SRE 负责人', channel: 'sms', timeout_min: 15 },
      ],
      channel_fallbacks: [
        { from: 'IM', to: 'sms' },
        { from: 'sms', to: 'phone' },
      ],
      enabled: true,
      created_at: isoAgo(60 * 24 * 40),
      updated_at: isoAgo(60 * 24 * 10),
    },
  ]
  db.notifications = [
    notif(
      1,
      'IM',
      'sre',
      'P1 支付网关 504 风暴 · 一级投递',
      'acked',
      210,
      undefined,
      961,
      1,
      isoAgo(190),
    ),
    notif(
      2,
      'IM',
      'admin',
      'P2 node-07 资源连锁 · 一级投递',
      'sent',
      65,
      undefined,
      961,
      1,
      isoAgo(60),
    ),
    notif(
      3,
      'IM',
      'ocm',
      'P2 node-07 资源连锁 · 二级投递（一级超时）',
      'queued',
      65,
      undefined,
      961,
      2,
      isoAgo(50),
    ),
    notif(
      4,
      'IM',
      'sre',
      'P3 结算接口 P99 劣化 · 通知',
      'acked',
      60 * 26,
      undefined,
      961,
      1,
      isoAgo(60 * 25),
    ),
    notif(
      5,
      'sms',
      '138xxxx0001',
      'P1 升级链三级投递（IM 两次失败降级）',
      'failed',
      210,
      undefined,
      961,
      3,
      isoAgo(175),
      '渠道超时（BR-13 降级链触发）',
    ),
  ]

  db.auditLogs = [
    audit(
      'system',
      'inspection.run.completed',
      'inspection_run',
      '621',
      { findings: 4, cluster: 'prod-cn-east-1' },
      isoAgo(36),
    ),
    audit(
      'sre',
      'alert.acknowledge',
      'alert',
      '201',
      { fingerprint: 'GatewayTimeout-pay' },
      isoAgo(95),
    ),
    audit(
      'admin',
      'policy.update',
      'inspection_policy',
      '611',
      { ai_explain_level: 'warning' },
      isoAgo(60 * 24),
    ),
    audit(
      'system',
      'ai.task.created',
      'ai_task',
      '403',
      { type: 'investigate', incident: 801 },
      isoAgo(8),
    ),
    audit(
      'admin',
      'user.create',
      'user',
      '4',
      { username: 'dev', roles: ['developer'] },
      isoAgo(60 * 24 * 5),
    ),
    audit('sre', 'finding.acknowledge', 'finding', '632', { rule_code: 'PVC_PENDING' }, isoAgo(30)),
  ]
}

// ---------- 构造辅助（保证必填字段齐全） ----------
function alert(
  id: number,
  fingerprint: string,
  severity: Alert['severity'],
  status: Alert['status'],
  team: string,
  count: number,
  title: string,
  minsAgo: number,
  enrichments: Record<string, string>,
  windowId?: number,
): Alert {
  const t = isoAgo(minsAgo)
  return {
    id,
    fingerprint: `${fingerprint}-${team}`,
    provider_id: 21,
    title,
    severity,
    status,
    labels: { alertname: fingerprint, team, ...enrichments },
    enrichments: { team, ...enrichments },
    occurrence_count: count,
    first_occurred_at: isoAgo(minsAgo + 30),
    last_occurred_at: t,
    assignee_id: status === 'notified' || status === 'correlated' ? undefined : 2,
    acknowledged_at:
      status === 'notified' || status === 'correlated' ? undefined : isoAgo(minsAgo - 1),
    resolved_at: status === 'resolved' ? t : undefined,
    suppressed_by_window_id: windowId,
    created_at: isoAgo(minsAgo + 30),
    updated_at: t,
  }
}

function incident(
  id: number,
  title: string,
  severity: Incident['severity'],
  status: Incident['status'],
  source: Incident['source'],
  team: string,
  synced: boolean,
  createdMinsAgo: number,
  updatedMinsAgo: number,
): Incident {
  return {
    id,
    title,
    severity,
    status,
    source,
    team,
    status_page_sync: synced,
    assignee_id: status === 'open' ? undefined : 2,
    cancelled_reason: status === 'cancelled' ? '变更窗口内预期告警' : undefined,
    acknowledged_at: ['acknowledged', 'mitigated', 'resolved', 'closed'].includes(status)
      ? isoAgo(updatedMinsAgo)
      : undefined,
    mitigated_at: ['mitigated', 'resolved', 'closed'].includes(status)
      ? isoAgo(updatedMinsAgo)
      : undefined,
    resolved_at: ['resolved', 'closed'].includes(status) ? isoAgo(updatedMinsAgo) : undefined,
    closed_at: status === 'closed' ? isoAgo(updatedMinsAgo) : undefined,
    created_at: isoAgo(createdMinsAgo),
    updated_at: isoAgo(updatedMinsAgo),
  }
}

function finding(
  id: number,
  runId: number,
  clusterId: number,
  ruleCode: string,
  kind: string,
  namespace: string,
  name: string,
  severity: Finding['severity'],
  status: Finding['status'],
  rawError: Record<string, unknown>,
  ignoreReason?: string,
): Finding {
  return {
    id,
    run_id: runId,
    cluster_id: clusterId,
    rule_code: ruleCode,
    resource_ref: { kind, namespace, name },
    severity,
    raw_error: rawError,
    status,
    ignored_reason: ignoreReason,
    created_at: isoAgo(35),
    updated_at: isoAgo(10),
  }
}

function aiTask(input: {
  id: number
  type: AITask['type']
  status: AITask['status']
  findingId?: number
  incidentId?: number
  callsUsed: number
  tokensUsed: number
  maxCalls: number
  maxTokens: number
  requiresApproval?: boolean
  createdAt: string
  finishedAt?: string
  approvalDeadline?: string
  error?: string
}): AITask {
  return {
    id: input.id,
    type: input.type,
    status: input.status,
    context_refs: {
      ...(input.findingId ? { finding_id: input.findingId } : {}),
      ...(input.incidentId ? { incident_id: input.incidentId } : {}),
    },
    finding_id: input.findingId,
    incident_id: input.incidentId,
    budget: { max_calls: input.maxCalls, max_output_tokens: input.maxTokens },
    calls_used: input.callsUsed,
    tokens_used: input.tokensUsed,
    requires_approval: input.requiresApproval ?? false,
    requested_by: 2,
    approval_deadline_at: input.approvalDeadline,
    is_partial: input.status === 'budget_exceeded',
    error: input.error,
    created_at: input.createdAt,
    updated_at: input.finishedAt ?? input.createdAt,
    finished_at: input.finishedAt,
  }
}

function callLog(
  id: number,
  taskId: number,
  model: string,
  tool: string | undefined,
  digest: string,
  tokensIn: number,
  tokensOut: number,
  latencyMs: number,
  resultCode: AICallLog['result_code'],
  createdAt = isoAgo(30),
  error?: string,
): AICallLog {
  return {
    id,
    task_id: taskId,
    model,
    tool_used: tool,
    prompt_digest: digest,
    tokens_in: tokensIn,
    tokens_out: tokensOut,
    latency_ms: latencyMs,
    result_code: resultCode,
    error,
    created_at: createdAt,
  }
}

function notif(
  id: number,
  channel: string,
  target: string,
  digestNote: string,
  status: NotificationRecord['status'],
  alertId?: number,
  incidentId?: number,
  policyId?: number,
  level?: number,
  at = isoAgo(20),
  error?: string,
): NotificationRecord {
  void digestNote
  return {
    id,
    channel,
    target,
    content_digest: `sha256:${id.toString(16).padStart(6, '0')}…`,
    status,
    ack_action: status === 'acked' ? 'Ack' : undefined,
    ack_at: status === 'acked' ? isoAgo(5) : undefined,
    alert_id: alertId,
    incident_id: incidentId,
    escalation_policy_id: policyId,
    escalation_level: level,
    error,
    created_at: at,
  }
}

function audit(
  actor: string,
  action: string,
  resourceType: string,
  resourceId: string,
  detail: Record<string, unknown>,
  at: string,
): AuditLog {
  return {
    id: nextId(),
    actor_user_id: actor === 'system' ? undefined : db.users.find((u) => u.username === actor)?.id,
    actor_type: actor === 'system' ? 'system' : 'user',
    action,
    resource_type: resourceType,
    resource_id: resourceId,
    detail,
    created_at: at,
  }
}
