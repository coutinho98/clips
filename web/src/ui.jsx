import { Loader2 } from 'lucide-react'

export function Panel({ children, className = '' }) {
  return <div className={`bg-bg-tertiary border border-border rounded-xl overflow-hidden ${className}`}>{children}</div>
}

export function PanelHeader({ children, className = '' }) {
  return <div className={`flex items-center justify-between px-4 py-3 border-b border-border shrink-0 ${className}`}>{children}</div>
}

export function PanelHeaderLeft({ icon: Icon, title, badge }) {
  return (
    <div className="flex items-center gap-2">
      {Icon && <Icon size={14} className="text-accent-light" />}
      <span className="text-xs font-semibold text-text">{title}</span>
      {badge !== undefined && (
        <span className="text-[10px] font-bold text-text-muted bg-bg px-1.5 py-0.5 rounded min-w-[18px] text-center">{badge}</span>
      )}
    </div>
  )
}

export function Button({ children, variant = 'default', size = 'md', className = '', ...props }) {
  const variants = {
    default: 'bg-bg-elevated border border-border text-text-secondary hover:text-text hover:border-border-light',
    primary: 'bg-accent text-white hover:bg-accent-hover border-transparent',
    ghost: 'text-text-secondary hover:text-text hover:bg-bg-hover border-transparent',
    danger: 'bg-danger/10 text-danger border border-danger/30 hover:bg-danger/20',
  }
  const sizes = {
    sm: 'px-2 py-1 text-[11px]',
    md: 'px-3 py-1.5 text-xs',
  }
  return (
    <button
      className={`flex items-center justify-center gap-1.5 rounded-md font-medium transition-all disabled:opacity-40 disabled:cursor-not-allowed ${variants[variant]} ${sizes[size]} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}

export function IconButton({ children, size = 28, className = '', ...props }) {
  return (
    <button
      className={`flex items-center justify-center rounded-md text-text-secondary hover:text-text hover:bg-bg-hover transition-all disabled:opacity-40 disabled:cursor-not-allowed ${className}`}
      style={{ width: size, height: size }}
      {...props}
    >
      {children}
    </button>
  )
}

export function FormLabel({ children, icon: Icon }) {
  return (
    <label className="flex items-center gap-1.5 text-[11px] font-medium text-text-secondary mb-1.5">
      {Icon && <Icon size={11} className="text-text-muted" />}
      {children}
    </label>
  )
}

export function FormInput({ className = '', ...props }) {
  return (
    <input
      className={`w-full px-2.5 py-1.5 bg-bg-elevated border border-border rounded-md text-xs text-text outline-none focus:border-accent min-w-0 transition-colors ${className}`}
      {...props}
    />
  )
}

export function FormSelect({ className = '', children, ...props }) {
  return (
    <select
      className={`w-full px-2.5 py-1.5 bg-bg-elevated border border-border rounded-md text-xs text-text outline-none focus:border-accent cursor-pointer transition-colors ${className}`}
      {...props}
    >
      {children}
    </select>
  )
}

export function RangeRow({ children }) {
  return <div className="flex items-center gap-2">{children}</div>
}

export function RangeInput({ className = '', ...props }) {
  return <input type="range" className={`flex-1 cursor-pointer accent-accent ${className}`} {...props} />
}

export function NumberInput({ className = '', ...props }) {
  return (
    <input
      type="number"
      className={`w-12 px-1 py-0.5 bg-bg-elevated border border-border rounded text-[11px] text-text text-center outline-none focus:border-accent min-w-0 ${className}`}
      {...props}
    />
  )
}

export function Toggle({ active, onClick }) {
  return (
    <div
      onClick={onClick}
      className={`w-8 h-4 rounded-full cursor-pointer transition-all ${active ? 'bg-accent' : 'bg-bg-elevated border border-border'}`}
    >
      <div className={`w-3 h-3 bg-white rounded-full m-0.5 transition-transform ${active ? 'translate-x-4' : ''}`} />
    </div>
  )
}

export function Spinner({ size = 14, className = '' }) {
  return <Loader2 size={size} className={`animate-spin ${className}`} />
}
