/**
 * LuxuryTable.tsx
 * ===============
 * Premium table component with:
 * - Luxury borders and shadows
 * - Hover effects with subtle lift
 * - Glass morphism headers
 * - Status badges with color coding
 * - RTL-aware layout
 */

import React from 'react'

interface TableColumn {
  key: string
  label: string
  render?: (value: any, row: any, index: number) => React.ReactNode
  align?: 'left' | 'center' | 'right'
  width?: string
}

interface LuxuryTableProps {
  columns: TableColumn[]
  data: any[]
  variant?: 'default' | 'glass' | 'premium'
  striped?: boolean
  className?: string
}

export const LuxuryTable: React.FC<LuxuryTableProps> = ({
  columns,
  data,
  variant = 'default',
  striped = true,
  className = '',
}) => {
  const headerClass = {
    default: 'bg-[var(--color-bg-primary)] border-b border-[var(--color-border-light)]',
    glass: 'glass-card border-b border-white/30',
    premium: 'bg-gradient-to-r from-[var(--color-brand-green)]/5 to-[var(--color-brand-gold)]/5 border-b-2 border-[var(--color-brand-green)]/20',
  }

  const rowClass = {
    default: 'border-b border-[var(--color-border-light)] hover:bg-[var(--color-bg-primary)] transition-colors',
    glass: 'border-b border-white/20 hover:bg-white/50 transition-all',
    premium: 'border-b border-[var(--color-border-luxury)] hover:bg-gradient-to-r hover:from-[var(--color-brand-green)]/5 hover:to-transparent transition-all',
  }

  return (
    <div className={`rounded-2xl overflow-hidden border ${
      variant === 'default' ? 'border-[var(--color-border-light)]' : 'border-[var(--color-border-luxury)]'
    } ${className}`}>
      {/* Table Wrapper */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          {/* Header */}
          <thead>
            <tr className={headerClass[variant]}>
              {columns.map(col => (
                <th
                  key={col.key}
                  className={`px-6 py-4 font-semibold text-[var(--color-text-primary)] ${
                    col.align === 'center' ? 'text-center' : 
                    col.align === 'right' ? 'text-end' : 'text-start'
                  }`}
                  style={{ width: col.width }}
                >
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>

          {/* Body */}
          <tbody>
            {data.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="px-6 py-12 text-center text-[var(--color-text-muted)]">
                  لا توجد بيانات للعرض
                </td>
              </tr>
            ) : (
              data.map((row, idx) => (
                <tr
                  key={idx}
                  className={`${rowClass[variant]} ${
                    striped && idx % 2 === 1 ? 'bg-[var(--color-bg-primary)]/50' : ''
                  }`}
                >
                  {columns.map(col => (
                    <td
                      key={`${idx}-${col.key}`}
                      className={`px-6 py-4 text-[var(--color-text-secondary)] ${
                        col.align === 'center' ? 'text-center' : 
                        col.align === 'right' ? 'text-end' : 'text-start'
                      }`}
                    >
                      {col.render ? col.render(row[col.key], row, idx) : row[col.key]}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export default LuxuryTable
