# KubeLantern 品牌资产

| 文件 | 用途 |
|---|---|
| `kubelanter-logo.svg` | 主标记：朱红渐变方标 + 灯笼轮廓 + Kubernetes 轮辐光核；用于 README、应用侧栏、登录页 |
| `kubelanter-lockup.svg` | 横版组合：主标记 + `KubeLantern` 字标 + `AI-NATIVE KUBERNETES SRE` 副标 |
| `kubelanter-mark-mono.svg` | 单色标记：灯笼使用 `currentColor`，适合深色背景或单色印刷 |
| `kubelanter-favicon.svg` | 16–32px 简化标记：去掉轮辐细节，保留灯笼与光核 |

## 色值

| 角色 | 色值 |
|---|---|
| 品牌主色 / 灯笼 | `#C53520` |
| 渐变亮部 | `#F0643C` |
| 渐变暗部 | `#8B1B0F` |
| 光核 / 强调 | `#F2CC60` |
| AI 能力 | `#9009E4` |
| 墨色文字 | `#191A1E` |

## 使用约束

- 主标记最小尺寸 16px；横版组合建议宽度 ≥ 200px。
- 标记四周留白不小于标记高度的 1/4；不要拉伸、旋转或改变渐变方向。
- 字标使用 Avenir Next Bold 转曲，避免部署环境缺字体时变形；正文仍使用 Inter / 系统无衬线。
- 应用内使用 `frontend/src/shared/ui/brand-logo.tsx` 的内联 SVG，与 `kubelanter-logo.svg` 保持同一几何与色值。
- `frontend/public/favicon.svg` 与 `kubelanter-favicon.svg` 为同一文件，构建时由 Vite 复制到站点根目录。
