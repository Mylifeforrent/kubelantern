import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useState, type JSX } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { login } from './api'
import { Button } from '../../shared/ui/button'
import { Input, Label } from '../../shared/ui/inputs'
import { BrandLogo } from '../../shared/ui/brand-logo'
import { describeProblem } from '../../shared/api/problem'

const schema = z.object({
  username: z.string().min(1, '请输入用户名'),
  loginPass: z.string().min(1, '请输入登录口令'),
})
type FormValues = z.infer<typeof schema>

/** 登录页（Blank 布局；形态随认证 [TBD-INFRA]，当前为占位表单）。
 *  真实后端 dev 认证：用户名取自 seed（admin / sre-tony / oncall-may / dev-lee / viewer-guest），
 *  口令统一为后端 .env 的 HUNTAI_DEV_AUTH_PASSWORD。 */
export function LoginForm(): JSX.Element {
  const { register, handleSubmit, formState } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { username: 'admin', loginPass: '' },
  })
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()
  const [params] = useSearchParams()

  const onSubmit = handleSubmit(async (v) => {
    setError(null)
    try {
      await login(v.username, v.loginPass)
      await navigate(params.get('next') ?? '/', { replace: true })
    } catch (e) {
      setError(describeProblem(e))
    }
  })

  return (
    <div className="h-full grid place-items-center">
      <form onSubmit={(e) => void onSubmit(e)} className="card w-[360px] p-6" noValidate>
        <div className="flex items-center gap-3 mb-5">
          <BrandLogo size={34} className="logo-mark" />
          <div>
            <b className="text-[15px] text-foreground block">KubeLantern</b>
            <span className="tiny text-tx2">Kubernetes SRE 智能运维平台</span>
          </div>
        </div>
        <div className="mb-3">
          <Label htmlFor="username">用户名</Label>
          <Input id="username" autoComplete="username" {...register('username')} />
        </div>
        <div className="mb-4">
          <Label htmlFor="loginPass">登录口令</Label>
          <Input
            id="loginPass"
            type="password"
            autoComplete="current-password"
            {...register('loginPass')}
          />
        </div>
        {error && (
          <p className="text-destructive text-[12.5px] mb-3" role="alert">
            {error}
          </p>
        )}
        <Button
          variant="primary"
          type="submit"
          className="w-full justify-center"
          disabled={formState.isSubmitting}
        >
          {formState.isSubmitting ? '登录中…' : '登录'}
        </Button>
        <p className="tiny text-dim mt-4 leading-relaxed">
          认证方式（SSO/LDAP/本地）待定稿 [TBD-INFRA]。dev 账号见后端 seed：admin / sre-tony /
          oncall-may / dev-lee / viewer-guest，口令为仓库根 .env 的 HUNTAI_DEV_AUTH_PASSWORD。
        </p>
      </form>
    </div>
  )
}
