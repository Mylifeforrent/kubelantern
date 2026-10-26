import { useCallback, useEffect, useState } from 'react'

type ProbeState = {
  state: 'loading' | 'ok' | 'error'
  detail: string
}

const JAVA_BASE = '/java'
const PYTHON_BASE = '/python'

async function probe(path: string): Promise<ProbeState> {
  try {
    const response = await fetch(path, { headers: { accept: 'application/json' } })
    const body = await response.text()
    if (!response.ok) {
      return { state: 'error', detail: `HTTP ${response.status} · ${body.slice(0, 240)}` }
    }
    return { state: 'ok', detail: body.slice(0, 400) }
  } catch (error) {
    return { state: 'error', detail: String(error) }
  }
}

function Card(props: {
  title: string
  subtitle: string
  probeState: ProbeState
  actions: { label: string; onClick: () => void }[]
}) {
  const { title, subtitle, probeState, actions } = props
  return (
    <section className="card">
      <header>
        <div>
          <h2>{title}</h2>
          <p>{subtitle}</p>
        </div>
        <span className={`pill ${probeState.state}`}>{probeState.state}</span>
      </header>
      <pre>{probeState.detail}</pre>
      <div className="actions">
        {actions.map((action) => (
          <button key={action.label} onClick={action.onClick}>
            {action.label}
          </button>
        ))}
      </div>
    </section>
  )
}

export default function App() {
  const [java, setJava] = useState<ProbeState>({ state: 'loading', detail: '探测中…' })
  const [python, setPython] = useState<ProbeState>({ state: 'loading', detail: '探测中…' })
  const [lastAction, setLastAction] = useState('尚未触发故障')

  const refresh = useCallback(async () => {
    setJava({ state: 'loading', detail: '探测中…' })
    setPython({ state: 'loading', detail: '探测中…' })
    const [javaState, pythonState] = await Promise.all([
      probe(`${JAVA_BASE}/api/orders`),
      probe(`${PYTHON_BASE}/api/inventory`),
    ])
    setJava(javaState)
    setPython(pythonState)
  }, [])

  useEffect(() => {
    void refresh()
  }, [refresh])

  const trigger = useCallback(async (path: string, label: string) => {
    setLastAction(`${label} → ${path}`)
    const state = await probe(path)
    setLastAction(`${label} → HTTP ${state.state === 'ok' ? '200' : '500'} · ${state.detail.slice(0, 180)}`)
  }, [])

  return (
    <main>
      <div className="hero">
        <div>
          <p className="eyebrow">KubeLantern · kind demo</p>
          <h1>业务服务控制台</h1>
          <p className="lead">
            这是部署在 kind 集群中的 React 演示应用。它会经 nginx 同源代理探测 Java 与 Python 服务，
            并可主动触发 5xx / 慢请求，供 KubeLantern 告警与巡检演示使用。
          </p>
        </div>
        <button className="primary" onClick={() => void refresh()}>
          重新探测
        </button>
      </div>

      <div className="grid">
        <Card
          title="Java 订单服务"
          subtitle="Spring Boot · /api/orders"
          probeState={java}
          actions={[
            { label: '触发 5xx', onClick: () => void trigger(`${JAVA_BASE}/api/orders/boom`, 'Java 5xx') },
            { label: '触发慢请求', onClick: () => void trigger(`${JAVA_BASE}/api/orders/slow?ms=1500`, 'Java slow') },
          ]}
        />
        <Card
          title="Python 库存服务"
          subtitle="FastAPI · /api/inventory"
          probeState={python}
          actions={[
            { label: '触发 5xx', onClick: () => void trigger(`${PYTHON_BASE}/api/inventory/boom`, 'Python 5xx') },
            { label: '触发慢请求', onClick: () => void trigger(`${PYTHON_BASE}/api/inventory/slow?ms=1500`, 'Python slow') },
          ]}
        />
      </div>

      <section className="log">
        <span>最近操作</span>
        <code>{lastAction}</code>
      </section>

      <footer>
        <span>KubeLantern 平台入口：<a href="http://localhost:8080">http://localhost:8080</a></span>
        <span>故障注入由 Helm values 控制：faults.enabled=true</span>
      </footer>
    </main>
  )
}
