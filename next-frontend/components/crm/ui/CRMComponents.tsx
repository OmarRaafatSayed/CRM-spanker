"""
TASK 9: UI Micro-Interactions & Dashboard Polish

Smooth framer/motion transitions, status badges, glassmorphic data tables,
and high-contrast typography for all CRM sub-routes.

Includes:
- Animated status badges
- Glassmorphic data tables
- Smooth page transitions
- High-contrast typography
- Micro-interactions
- Responsive design
"""

import React, { ReactNode } from 'react';
import { motion } from 'framer-motion';

// ─────────────────────────────────────────────────────────────────────────────
// Animation Variants
// ─────────────────────────────────────────────────────────────────────────────

export const pageVariants = {
  initial: { opacity: 0, y: 20 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -20 }
};

export const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.1
    }
  }
};

export const itemVariants = {
  hidden: { opacity: 0, y: 10 },
  visible: { opacity: 1, y: 0 }
};

export const badgeVariants = {
  initial: { scale: 0.8, opacity: 0 },
  animate: { scale: 1, opacity: 1 },
  hover: { scale: 1.05 },
  tap: { scale: 0.95 }
};

export const tableRowVariants = {
  hidden: { opacity: 0, x: -10 },
  visible: (i: number) => ({
    opacity: 1,
    x: 0,
    transition: { delay: i * 0.05 }
  }),
  hover: { backgroundColor: 'rgba(255, 255, 255, 0.05)' }
};

// ─────────────────────────────────────────────────────────────────────────────
// Status Badge Component
// ─────────────────────────────────────────────────────────────────────────────

type StatusType = 'active' | 'inactive' | 'pending' | 'in_progress' | 'completed' | 'failed' | 'approved' | 'rejected';

const statusConfig: Record<StatusType, { color: string; bgColor: string; icon: string }> = {
  active: { color: '#10b981', bgColor: 'rgba(16, 185, 129, 0.1)', icon: '●' },
  inactive: { color: '#6b7280', bgColor: 'rgba(107, 114, 128, 0.1)', icon: '○' },
  pending: { color: '#f59e0b', bgColor: 'rgba(245, 158, 11, 0.1)', icon: '⏱' },
  in_progress: { color: '#3b82f6', bgColor: 'rgba(59, 130, 246, 0.1)', icon: '⟳' },
  completed: { color: '#10b981', bgColor: 'rgba(16, 185, 129, 0.1)', icon: '✓' },
  failed: { color: '#ef4444', bgColor: 'rgba(239, 68, 68, 0.1)', icon: '✕' },
  approved: { color: '#10b981', bgColor: 'rgba(16, 185, 129, 0.1)', icon: '✓' },
  rejected: { color: '#ef4444', bgColor: 'rgba(239, 68, 68, 0.1)', icon: '✕' }
};

export const StatusBadge: React.FC<{
  status: StatusType;
  label?: string;
  animated?: boolean;
}> = ({ status, label, animated = true }) => {
  const config = statusConfig[status];

  return (
    <motion.div
      variants={animated ? badgeVariants : {}}
      initial={animated ? 'initial' : false}
      animate={animated ? 'animate' : false}
      whileHover={animated ? 'hover' : {}}
      whileTap={animated ? 'tap' : {}}
      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold"
      style={{
        color: config.color,
        backgroundColor: config.bgColor,
        border: `1.5px solid ${config.color}`,
        transition: 'all 0.2s ease-out'
      }}
    >
      {animated && (
        <motion.span
          animate={{ rotate: 360 }}
          transition={status === 'in_progress' ? { repeat: Infinity, duration: 2 } : {}}
        >
          {config.icon}
        </motion.span>
      )}
      {label || status.replace(/_/g, ' ').toUpperCase()}
    </motion.div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Glassmorphic Data Table
// ─────────────────────────────────────────────────────────────────────────────

interface TableColumn {
  key: string;
  label: string;
  width?: string;
  render?: (value: any, row: any) => ReactNode;
  sortable?: boolean;
}

export const GlassmorphicTable: React.FC<{
  columns: TableColumn[];
  data: any[];
  rowVariant?: any;
  onRowClick?: (row: any) => void;
}> = ({ columns, data, rowVariant = tableRowVariants, onRowClick }) => {
  return (
    <motion.div
      variants={containerVariants}
      initial="hidden"
      animate="visible"
      className="rounded-xl overflow-hidden"
      style={{
        background: 'rgba(255, 255, 255, 0.08)',
        backdropFilter: 'blur(10px)',
        border: '1px solid rgba(255, 255, 255, 0.2)',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)'
      }}
    >
      {/* Header */}
      <div className="grid gap-4 p-4 border-b border-white/10" style={{
        gridTemplateColumns: columns.map(c => c.width || '1fr').join(' ')
      }}>
        {columns.map(col => (
          <div
            key={col.key}
            className="text-xs font-bold uppercase tracking-wider text-white/80"
          >
            {col.label}
          </div>
        ))}
      </div>

      {/* Rows */}
      <div>
        {data.map((row, idx) => (
          <motion.div
            key={idx}
            custom={idx}
            variants={rowVariant}
            initial="hidden"
            animate="visible"
            whileHover="hover"
            onClick={() => onRowClick?.(row)}
            className="grid gap-4 p-4 border-b border-white/5 hover:bg-white/5 cursor-pointer transition-colors"
            style={{
              gridTemplateColumns: columns.map(c => c.width || '1fr').join(' ')
            }}
          >
            {columns.map(col => (
              <div key={`${col.key}-${idx}`} className="text-sm text-white/90 truncate">
                {col.render ? col.render(row[col.key], row) : row[col.key]}
              </div>
            ))}
          </motion.div>
        ))}
      </div>

      {data.length === 0 && (
        <div className="p-8 text-center text-white/50">
          No data available
        </div>
      )}
    </motion.div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Animated Metric Card
// ─────────────────────────────────────────────────────────────────────────────

export const MetricCard: React.FC<{
  label: string;
  value: string | number;
  icon?: ReactNode;
  change?: { value: number; isPositive: boolean };
  animated?: boolean;
}> = ({ label, value, icon, change, animated = true }) => {
  return (
    <motion.div
      variants={itemVariants}
      className="rounded-xl p-6"
      style={{
        background: 'rgba(255, 255, 255, 0.08)',
        backdropFilter: 'blur(10px)',
        border: '1px solid rgba(255, 255, 255, 0.2)',
        boxShadow: '0 8px 32px rgba(0, 0, 0, 0.1)'
      }}
      whileHover={{ scale: 1.02, boxShadow: '0 12px 48px rgba(0, 0, 0, 0.15)' }}
      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
    >
      <div className="flex items-start justify-between mb-4">
        <span className="text-xs font-semibold uppercase text-white/60">{label}</span>
        {icon && <div className="text-2xl text-blue-400">{icon}</div>}
      </div>

      <div className="flex items-end gap-2">
        <motion.div
          className="text-3xl font-bold text-white"
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.1 }}
        >
          {value}
        </motion.div>

        {change && (
          <motion.div
            className={`text-xs font-semibold ${
              change.isPositive ? 'text-green-400' : 'text-red-400'
            }`}
            initial={{ opacity: 0, y: 5 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
          >
            {change.isPositive ? '↑' : '↓'} {Math.abs(change.value)}%
          </motion.div>
        )}
      </div>
    </motion.div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Animated Page Header
// ─────────────────────────────────────────────────────────────────────────────

export const PageHeader: React.FC<{
  title: string;
  subtitle?: string;
  icon?: ReactNode;
  action?: ReactNode;
}> = ({ title, subtitle, icon, action }) => {
  return (
    <motion.div
      variants={pageVariants}
      initial="initial"
      animate="animate"
      className="mb-8"
    >
      <div className="flex items-center justify-between gap-4 mb-4">
        <div className="flex items-center gap-3">
          {icon && (
            <motion.div
              initial={{ scale: 0, rotate: -180 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ type: 'spring', stiffness: 200 }}
              className="text-4xl"
            >
              {icon}
            </motion.div>
          )}
          <div>
            <h1 className="text-3xl font-bold text-white">{title}</h1>
            {subtitle && <p className="text-white/60 mt-1">{subtitle}</p>}
          </div>
        </div>
        {action && (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
          >
            {action}
          </motion.div>
        )}
      </div>
    </motion.div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Loading Skeleton
// ─────────────────────────────────────────────────────────────────────────────

export const SkeletonLoader: React.FC<{ count?: number }> = ({ count = 5 }) => {
  return (
    <div className="space-y-4">
      {Array.from({ length: count }).map((_, i) => (
        <motion.div
          key={i}
          animate={{ opacity: [0.5, 1, 0.5] }}
          transition={{ repeat: Infinity, duration: 1.5 }}
          className="h-12 rounded-lg"
          style={{
            background: 'rgba(255, 255, 255, 0.1)',
            backdropFilter: 'blur(10px)'
          }}
        />
      ))}
    </div>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Animated Button
// ─────────────────────────────────────────────────────────────────────────────

export const AnimatedButton: React.FC<{
  label: string;
  onClick?: () => void;
  variant?: 'primary' | 'secondary' | 'danger';
  loading?: boolean;
  disabled?: boolean;
}> = ({ label, onClick, variant = 'primary', loading, disabled }) => {
  const variants: Record<string, { bg: string; hover: string }> = {
    primary: { bg: 'bg-blue-600', hover: 'hover:bg-blue-700' },
    secondary: { bg: 'bg-white/20', hover: 'hover:bg-white/30' },
    danger: { bg: 'bg-red-600', hover: 'hover:bg-red-700' }
  };

  const style = variants[variant];

  return (
    <motion.button
      onClick={onClick}
      disabled={disabled || loading}
      className={`
        px-6 py-2 rounded-lg font-semibold text-white
        transition-colors duration-200
        ${style.bg} ${!disabled ? style.hover : 'opacity-50 cursor-not-allowed'}
      `}
      whileHover={!disabled ? { scale: 1.05 } : {}}
      whileTap={!disabled ? { scale: 0.95 } : {}}
    >
      {loading ? (
        <motion.span
          animate={{ rotate: 360 }}
          transition={{ repeat: Infinity, duration: 1 }}
        >
          ⟳
        </motion.span>
      ) : (
        label
      )}
    </motion.button>
  );
};

// ─────────────────────────────────────────────────────────────────────────────
// Modal Overlay
// ─────────────────────────────────────────────────────────────────────────────

export const ModalOverlay: React.FC<{
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  actions?: ReactNode;
}> = ({ isOpen, onClose, title, children, actions }) => {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: isOpen ? 1 : 0 }}
      exit={{ opacity: 0 }}
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{
        background: 'rgba(0, 0, 0, 0.5)',
        backdropFilter: 'blur(5px)'
      }}
      pointerEvents={isOpen ? 'auto' : 'none'}
    >
      <motion.div
        initial={{ scale: 0.9, opacity: 0 }}
        animate={{ scale: isOpen ? 1 : 0.9, opacity: isOpen ? 1 : 0 }}
        exit={{ scale: 0.9, opacity: 0 }}
        onClick={(e) => e.stopPropagation()}
        className="rounded-xl p-6 max-w-md w-full"
        style={{
          background: 'rgba(30, 30, 40, 0.95)',
          backdropFilter: 'blur(20px)',
          border: '1px solid rgba(255, 255, 255, 0.2)'
        }}
      >
        <h2 className="text-xl font-bold text-white mb-4">{title}</h2>
        <div className="text-white/80 mb-6">{children}</div>
        {actions && <div className="flex gap-3">{actions}</div>}
      </motion.div>
    </motion.div>
  );
};
