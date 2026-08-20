import { useQuery } from '@tanstack/react-query'
import { 
  FileSearch, 
  FileText, 
  CheckCircle2, 
  XCircle, 
  Zap, 
  Bell
} from 'lucide-react'
import { getStats, getNotifications } from '../../lib/api'
import { PageHeader } from '../../components/ui-kit/PageHeader'
import { cn } from '@/lib/utils'

function StatCard({ title, value, icon: Icon, colorClass, loading }: { title: string, value: string | number, icon: any, colorClass: string, loading: boolean }) {
  return (
    <div className="glass-card relative overflow-hidden p-5">
      <div className={cn("absolute right-0 top-0 h-24 w-24 -translate-y-8 translate-x-8 rounded-full opacity-10 blur-2xl", colorClass)} />
      <div className="flex items-center gap-4">
        <div className={cn("flex size-12 shrink-0 items-center justify-center rounded-lg bg-opacity-10", colorClass.replace('bg-', 'text-').replace('500', '600'), colorClass.replace('500', '100'))}>
          <Icon size={24} />
        </div>
        <div className="flex flex-col">
          <span className="text-sm font-semibold text-muted-foreground">{title}</span>
          {loading ? (
             <div className="mt-1 h-8 w-16 animate-pulse rounded bg-muted" />
          ) : (
            <span className="text-2xl font-extrabold tracking-tight">{value}</span>
          )}
        </div>
      </div>
    </div>
  )
}

function CycleCard({ cycleName, data }: { cycleName: string, data: any }) {
  let statusColor = "bg-slate-500"
  let statusText = "No GMF"
  
  if (data?.status === 'completed') {
    statusColor = "bg-emerald-500"
    statusText = "Completed"
  } else if (data?.status === 'generating') {
    statusColor = "bg-amber-500 animate-pulse"
    statusText = "Generating"
  } else if (data?.status === 'approved') {
    statusColor = "bg-emerald-500"
    statusText = "Approved"
  } else if (data?.status === 'pending') {
    statusColor = "bg-cyan-500"
    statusText = "Pending Review"
  }

  return (
    <div className="glass-card flex items-center justify-between p-4">
      <div className="flex items-center gap-3">
        <div className={cn("size-3 rounded-full", statusColor)} />
        <span className="font-semibold">{cycleName.replace('_', ' ')}</span>
      </div>
      <div className="flex flex-col items-end text-sm">
        <span className="text-muted-foreground">{data?.received || 0} GMFs received</span>
        <span className="font-medium">{statusText}</span>
      </div>
    </div>
  )
}

function EventIcon({ type }: { type: string }) {
  switch (type) {
    case 'GMF_DETECTED': return <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-cyan-100 text-cyan-600"><FileSearch size={14} /></div>
    case 'TEST_GMF_RECEIVED': return <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-indigo-600"><FileText size={14} /></div>
    case 'APPROVED': return <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-emerald-100 text-emerald-600"><CheckCircle2 size={14} /></div>
    case 'REJECTED': return <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-rose-100 text-rose-600"><XCircle size={14} /></div>
    default: return <div className="flex size-8 shrink-0 items-center justify-center rounded-full bg-slate-100 text-slate-600"><Bell size={14} /></div>
  }
}

export default function Admin1Dashboard() {
  const { data: stats, isLoading: loadingStats } = useQuery({
    queryKey: ['billing-stats'],
    queryFn: getStats,
    refetchInterval: 3000,
  })

  const { data: events, isLoading: loadingEvents } = useQuery({
    queryKey: ['billing-events'],
    queryFn: () => getNotifications(false),
    refetchInterval: 3000,
  })

  return (
    <div className="space-y-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <PageHeader 
          title="Dashboard Overview" 
          description="GMF upload statistics and sync status" 
        />
        {/* <Button 
          onClick={() => scanMutation.mutate()} 
          disabled={scanMutation.isPending}
          className="flex items-center gap-2"
        >
          <RefreshCw className={cn("size-4", scanMutation.isPending && "animate-spin")} />
          Scan Google Drive Folder
        </Button> */}
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard 
          title="GMFs Today" 
          value={stats?.gmfs_received_today || 0} 
          icon={FileSearch} 
          colorClass="bg-cyan-500" 
          loading={loadingStats} 
        />
        <StatCard 
          title="Pending Approval" 
          value={stats?.gmfs_pending_review || 0} 
          icon={Zap} 
          colorClass="bg-amber-500" 
          loading={loadingStats} 
        />
        {/* <StatCard 
          title="Google Drive Watch" 
          value={"Connected & Watching..."} 
          icon={Cloud} 
          colorClass="bg-emerald-500" 
          loading={false} 
        /> */}
      </div>

      <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
        {/* Left Column: Cycles */}
        <div className="flex flex-col gap-4 lg:col-span-1">
          <h3 className="text-lg font-semibold tracking-tight">Active Folders</h3>
          <div className="flex flex-col gap-3">
            {['Cycle_1', 'Cycle_2', 'Cycle_3', 'Cycle_4', 'Test_GMFs'].map(key => {
              return (
                <CycleCard 
                  key={key} 
                  cycleName={key} 
                  data={stats?.cycles?.[key]} 
                />
              )
            })}
          </div>
        </div>

        {/* Right Column: Activity Feed */}
        <div className="flex flex-col gap-4 lg:col-span-2">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold tracking-tight">Live Activity Feed</h3>
          </div>
          
          <div className="rounded-xl border bg-card shadow-sm">
            {loadingEvents ? (
              <div className="flex flex-col gap-4 p-6">
                {[1,2,3].map(i => (
                  <div key={i} className="flex gap-4">
                    <div className="size-8 shrink-0 animate-pulse rounded-full bg-muted" />
                    <div className="flex-1 space-y-2">
                      <div className="h-4 w-1/3 animate-pulse rounded bg-muted" />
                      <div className="h-3 w-2/3 animate-pulse rounded bg-muted" />
                    </div>
                  </div>
                ))}
              </div>
            ) : events?.length === 0 ? (
              <div className="flex items-center justify-center p-8 text-sm text-muted-foreground">
                No recent activity.
              </div>
            ) : (
              <div className="flex max-h-[400px] flex-col overflow-auto p-2">
                {events?.slice(0, 10).map((event) => (
                  <div key={event.id} className="flex gap-4 rounded-lg p-3 hover:bg-muted/50 transition-colors">
                    <EventIcon type={event.event_type} />
                    <div className="flex flex-col">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-sm">{event.title}</span>
                        <span className="text-xs text-muted-foreground">
                          {new Date(event.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      <span className="text-sm text-muted-foreground mt-0.5">{event.message}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
