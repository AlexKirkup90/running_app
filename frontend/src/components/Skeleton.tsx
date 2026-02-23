export function Skeleton({ className = '' }: { className?: string }) {
  return <div className={`animate-pulse rounded bg-slate-700 ${className}`} />
}
