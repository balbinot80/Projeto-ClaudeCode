import { cn } from '@/lib/utils'

export function Skeleton({ className }: { className?: string }) {
  return (
    <div className={cn('au-skeleton rounded-lg', className)} />
  )
}

export function SkeletonCard() {
  return (
    <div className="rounded-2xl p-5 flex flex-col gap-4"
         style={{ background: 'var(--au-surface)', border: '1px solid var(--au-border)', boxShadow: '0 2px 16px rgba(171,103,116,.07)' }}>
      <div className="flex items-center gap-2">
        <Skeleton className="w-1 h-4" />
        <Skeleton className="h-3 w-28" />
      </div>
      <div className="flex flex-col gap-1">
        <Skeleton className="h-9 w-32" />
        <Skeleton className="h-px w-full mt-2" />
        <Skeleton className="h-7 w-full mt-1" />
        <Skeleton className="h-7 w-full" />
        <Skeleton className="h-7 w-full" />
      </div>
    </div>
  )
}
