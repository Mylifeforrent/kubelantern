/** 抑制建议弹窗（告警处置流：误报走抑制建议入降噪反馈池）。
 *  三原因单选 + 补充说明；原因值域以契约为准（SuppressSuggestionReason）。 */
import { useState, type JSX } from 'react'
import { useSearchParams } from 'react-router'
import { Modal } from '../../../shared/ui/overlays'
import { Button } from '../../../shared/ui/button'
import { RadioCards, Label, Textarea } from '../../../shared/ui/inputs'
import { Icon } from '../../../shared/ui/icon'
import type { SuppressSuggestionReason } from '../../../shared/api/types'
import { useSuppressSuggestion } from '../api'

const REASONS: { value: SuppressSuggestionReason; label: string; description: string }[] = [
  {
    value: 'false_positive',
    label: '误报',
    description: '告警描述的现象实际未发生或不符合预期语义',
  },
  {
    value: 'expected_noise',
    label: '预期内噪声',
    description: '变更/发布窗口内的预期告警，无需值班响应',
  },
  { value: 'duplicate_rule', label: '规则重复', description: '与其他告警源重复，应并入既有规则' },
]

export function SuppressModal({ alertId }: { alertId: number }): JSX.Element | null {
  const [reason, setReason] = useState<SuppressSuggestionReason | ''>('')
  const [note, setNote] = useState('')
  const [params, setParams] = useSearchParams()
  const mutate = useSuppressSuggestion()
  if (!params.get('suppress')) return null

  const close = () =>
    setParams((p) => {
      const next = new URLSearchParams(p)
      next.delete('suppress')
      return next
    })

  return (
    <Modal
      open
      onClose={close}
      label="抑制建议"
      title={
        <>
          <Icon name="x" size={15} className="text-tx2" /> 抑制建议 · 告警 #{alertId}
        </>
      }
      footer={
        <>
          <Button onClick={close}>取消</Button>
          <Button
            variant="primary"
            disabled={!reason || mutate.isPending}
            onClick={() => {
              if (!reason) return
              mutate.mutate(
                { id: alertId, body: { reason, note: note || undefined } },
                { onSuccess: close },
              )
            }}
          >
            提交建议
          </Button>
        </>
      }
    >
      <RadioCards
        name="suppress-reason"
        value={reason}
        onChange={(v) => setReason(v as SuppressSuggestionReason)}
        options={REASONS}
        ariaLabel="抑制原因"
      />
      <div>
        <Label htmlFor="suppress-note">补充说明（可选）</Label>
        <Textarea
          id="suppress-note"
          rows={3}
          maxLength={500}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="补充上下文，帮助规则调优复核（例如关联的变更单）"
        />
      </div>
      <p className="tiny text-dim">
        提交后进入降噪反馈池，由规则调优复核；本操作计入审计（BR-10）。
      </p>
    </Modal>
  )
}
