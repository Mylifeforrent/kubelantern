/** 数据表格（hifi §4.4 + 03-frontend-design §1.2.6：TanStack Table 统一列表）。
 *  行组件由调用方以 cell 渲染；行点击与高亮行（pending_approval）由 props 注入；
 *  超过 100 行启用虚拟滚动为 P0 工程化项（§6 预算），当前数据面在阈值内。 */
import {
  flexRender,
  getCoreRowModel,
  useReactTable,
  type ColumnDef,
  type Row,
} from '@tanstack/react-table'
import type { JSX } from 'react'
import { Empty } from './data'

interface DataTableProps<T> {
  columns: ColumnDef<T, unknown>[]
  data: T[]
  onRowClick?: (row: Row<T>) => void
  rowClass?: (row: Row<T>) => string | undefined
  ariaLabel: string
  emptyText: string
}

export function DataTable<T>({
  columns,
  data,
  onRowClick,
  rowClass,
  ariaLabel,
  emptyText,
}: DataTableProps<T>): JSX.Element {
  const table = useReactTable({
    data,
    columns,
    getCoreRowModel: getCoreRowModel(),
  })

  if (data.length === 0) {
    return <Empty text={emptyText} />
  }

  return (
    <div className="overflow-x-auto">
      <table className="tbl" aria-label={ariaLabel}>
        <thead>
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((h) => (
                <th key={h.id}>{flexRender(h.column.columnDef.header, h.getContext())}</th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => (
            <tr
              key={row.id}
              className={
                [onRowClick ? 'click' : '', rowClass?.(row) ?? ''].filter(Boolean).join(' ') ||
                undefined
              }
              onClick={onRowClick ? () => onRowClick(row) : undefined}
            >
              {row.getVisibleCells().map((cell) => (
                <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
