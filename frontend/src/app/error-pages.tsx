/** 错误页（Blank 布局）：403 权限不足 / 404 未找到。 */
import type { JSX } from 'react'
import { Link } from 'react-router'
import { Icon } from '../shared/ui/icon'
import { Button } from '../shared/ui/button'

function Blank({ code, title, sub }: { code: string; title: string; sub: string }): JSX.Element {
  return (
    <div className="h-full grid place-items-center">
      <div className="card w-[380px] p-8 text-center">
        <div className="text-dim flex justify-center mb-3">
          <Icon name="warn" size={28} />
        </div>
        <div className="num text-[22px] font-semibold text-foreground">{code}</div>
        <div className="text-[13px] text-body mt-1">{title}</div>
        <p className="tiny text-dim mt-2">{sub}</p>
        <div className="mt-4 flex justify-center gap-2">
          <Link to="/alerts">
            <Button>返回工作台</Button>
          </Link>
          <Link to="/login">
            <Button variant="primary">重新登录</Button>
          </Link>
        </div>
      </div>
    </div>
  )
}

export function ForbiddenPage(): JSX.Element {
  return (
    <Blank
      code="403"
      title="当前角色无权访问该页面"
      sub="路由可见性由角色权限矩阵控制（领域 §3）；数据边界由后端权威执行"
    />
  )
}

export function NotFoundPage(): JSX.Element {
  return <Blank code="404" title="页面不存在" sub="请检查地址，或从侧栏导航进入对应工作台" />
}
