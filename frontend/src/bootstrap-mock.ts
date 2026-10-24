/** mock 装配（阶段一 S2）：必须是 main.tsx 的第一个 import。
 *  依赖 ESM 副作用求值顺序：本模块先于 router 等一切 app 模块顶层代码执行，
 *  保证 createBrowserRouter 初始化触发的 loader 请求也能被 mock 拦截。 */
import { installMock } from './shared/api/mock'

installMock()
