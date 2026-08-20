import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  getUsers,
  createUser,
  deleteUser,
  getPermissionRequests,
  approvePermissionRequest,
  rejectPermissionRequest,
  getUserActivity,
} from '../../lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import {
  Users,
  UserPlus,
  Trash2,
  Shield,
  CheckCircle,
  Search,
  RefreshCw,
  Activity,
  Lock,
  Mail,
  UserCheck,
  ClipboardList,
  CheckCircle2,
  XCircle,
  X,
  Clock,
  Eye,
} from 'lucide-react'
import { toast } from 'sonner'

type Tab = 'users' | 'requests' | 'activity'

const roleBadges: Record<string, { label: string; class: string }> = {
  ADMIN:            { label: 'Admin',           class: 'bg-slate-500/15 text-slate-300 border-slate-500/30' },
  GMF_HANDLER:      { label: 'GMF Handler',     class: 'bg-[#0066b3]/15 text-[#00b2e3] border-[#0066b3]/30' },
  ADMIN1:           { label: 'GMF Handler',     class: 'bg-[#0066b3]/15 text-[#00b2e3] border-[#0066b3]/30' },
  ENVELOPE_HANDLER: { label: 'Envelope Handler',class: 'bg-purple-500/15 text-purple-300 border-purple-500/30' },
  MANAGER:          { label: 'User Manager',    class: 'bg-[#00a651]/15 text-[#00e676] border-[#00a651]/30' },
  CUSTOMER:         { label: 'Customer',        class: 'bg-amber-500/15 text-amber-300 border-amber-500/30' },
}

const requestStatusBadge: Record<string, { label: string; class: string; Icon: any }> = {
  PENDING:  { label: 'Pending',  class: 'bg-amber-500/15 text-amber-300 border-amber-500/30',  Icon: Clock },
  APPROVED: { label: 'Approved', class: 'bg-[#00a651]/15 text-[#00e676] border-[#00a651]/30', Icon: CheckCircle2 },
  REJECTED: { label: 'Rejected', class: 'bg-red-500/15 text-red-400 border-red-500/30',        Icon: XCircle },
}

export default function ManagerDashboard() {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<Tab>('users')
  const [search, setSearch] = useState('')
  const [showAddModal, setShowAddModal] = useState(false)
  const [emailInput, setEmailInput] = useState('')
  const [selectedRoles, setSelectedRoles] = useState<string[]>(['GMF_HANDLER'])
  const [rejectNoteModal, setRejectNoteModal] = useState<{ id: number; email: string } | null>(null)
  const [rejectNote, setRejectNote] = useState('')
  const [activityModal, setActivityModal] = useState<{ userId: number; email: string } | null>(null)

  // Portal options for multi-select provisioning (no auto-expansion — each is a standalone grant)
  const PORTAL_OPTIONS = [
    { value: 'ADMIN',            label: 'ADMIN',            color: 'text-slate-300',  borderColor: 'border-slate-500/40', bg: 'bg-slate-500/10' },
    { value: 'GMF_HANDLER',      label: 'GMF',              color: 'text-[#00b2e3]',  borderColor: 'border-[#0066b3]/40', bg: 'bg-[#0066b3]/10' },
    { value: 'ENVELOPE_HANDLER', label: 'ENVELOP HANDLER',  color: 'text-purple-300', borderColor: 'border-purple-500/40', bg: 'bg-purple-500/10' },
    { value: 'MANAGER',          label: 'USER MANAGER',     color: 'text-[#00e676]',  borderColor: 'border-[#00a651]/40', bg: 'bg-[#00a651]/10' },
  ] as const

  // ── Queries ──────────────────────────────────────────────────────────────

  const { data: users = [], isLoading: usersLoading, refetch: refetchUsers } = useQuery({
    queryKey: ['users'],
    queryFn: getUsers,
  })

  const { data: requests = [], isLoading: requestsLoading, refetch: refetchRequests } = useQuery({
    queryKey: ['permission-requests'],
    queryFn: getPermissionRequests,
    enabled: activeTab === 'requests',
  })

  const { data: activity } = useQuery({
    queryKey: ['user-activity', activityModal?.userId],
    queryFn: () => getUserActivity(activityModal!.userId),
    enabled: !!activityModal,
  })

  // ── Mutations ────────────────────────────────────────────────────────────

  const createMutation = useMutation({
    mutationFn: createUser,
    onSuccess: (data) => {
      toast.success(`Provisioned user ${data.email}`)
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setShowAddModal(false)
      setEmailInput('')
      setSelectedRoles(['GMF_HANDLER'])
    },
    onError: (err: any) => toast.error(err?.detail || 'Failed to create user'),
  })

  const deleteMutation = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => {
      toast.success('User access revoked')
      queryClient.invalidateQueries({ queryKey: ['users'] })
    },
    onError: (err: any) => toast.error(err?.detail || 'Failed to delete user'),
  })

  const approveMutation = useMutation({
    mutationFn: approvePermissionRequest,
    onSuccess: (data) => {
      toast.success(`Access approved for ${data.email}`)
      queryClient.invalidateQueries({ queryKey: ['permission-requests'] })
      queryClient.invalidateQueries({ queryKey: ['users'] })
    },
    onError: (err: any) => toast.error(err?.detail || 'Failed to approve'),
  })

  const rejectMutation = useMutation({
    mutationFn: ({ id, note }: { id: number; note?: string }) =>
      rejectPermissionRequest(id, note),
    onSuccess: (data) => {
      toast.success(`Request from ${data.email} rejected`)
      queryClient.invalidateQueries({ queryKey: ['permission-requests'] })
      setRejectNoteModal(null)
      setRejectNote('')
    },
    onError: (err: any) => toast.error(err?.detail || 'Failed to reject'),
  })

  // ── Helpers ──────────────────────────────────────────────────────────────

  function handleCreateUser(e: React.FormEvent) {
    e.preventDefault()
    if (!emailInput.trim()) return
    if (selectedRoles.length === 0) {
      toast.error('Please select at least one portal.')
      return
    }
    createMutation.mutate({
      email: emailInput.trim(),
      role: selectedRoles[0],
      roles: selectedRoles,
      is_active: true,
    })
  }

  const filteredUsers = users.filter((u) =>
    u.email.toLowerCase().includes(search.toLowerCase()) ||
    u.role.toLowerCase().includes(search.toLowerCase())
  )

  const pendingCount = requests.filter(r => r.status === 'PENDING').length

  // ── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6 max-w-7xl mx-auto">

      {/* Header Banner */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 glass-card p-6 rounded-2xl border border-border/50 bg-background/60 backdrop-blur-xl">
        <div className="flex items-center gap-4">
          <div className="flex size-14 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-[#00a651] to-teal-600 text-white shadow-lg shadow-[#00a651]/25">
            <Users size={28} />
          </div>
          <div>
            <h1 className="text-2xl font-extrabold text-foreground tracking-tight">User Access Management</h1>
            <p className="text-sm font-medium text-muted-foreground">
              Provision staff SSO accounts, assign access roles, review permission requests.
            </p>
          </div>
        </div>
        <Button
          onClick={() => setShowAddModal(true)}
          className="h-11 rounded-xl bg-gradient-to-r from-[#00a651] to-teal-600 font-extrabold text-white shadow-lg shadow-[#00a651]/25 hover:opacity-90 transition-all border-none"
        >
          <UserPlus size={18} className="mr-2" />
          Provision New Staff
        </Button>
      </div>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-4">
        <Card className="glass-card border-border/40 bg-background/50">
          <CardContent className="p-5 flex items-center justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Total Staff</p>
              <p className="text-3xl font-extrabold text-foreground mt-1">{users.length}</p>
            </div>
            <div className="size-12 rounded-xl bg-muted flex items-center justify-center text-foreground">
              <UserCheck size={22} />
            </div>
          </CardContent>
        </Card>
        <Card className="glass-card border-border/40 bg-background/50">
          <CardContent className="p-5 flex items-center justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">GMF Handlers</p>
              <p className="text-3xl font-extrabold text-[#00b2e3] mt-1">
                {users.filter(u => ['GMF_HANDLER', 'ADMIN1'].includes(u.role)).length}
              </p>
            </div>
            <div className="size-12 rounded-xl bg-[#0066b3]/10 text-[#00b2e3] flex items-center justify-center">
              <Shield size={22} />
            </div>
          </CardContent>
        </Card>
        <Card className="glass-card border-border/40 bg-background/50">
          <CardContent className="p-5 flex items-center justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">User Managers</p>
              <p className="text-3xl font-extrabold text-[#00a651] mt-1">
                {users.filter(u => u.role === 'MANAGER').length}
              </p>
            </div>
            <div className="size-12 rounded-xl bg-[#00a651]/10 text-[#00a651] flex items-center justify-center">
              <Lock size={22} />
            </div>
          </CardContent>
        </Card>
        <Card className="glass-card border-border/40 bg-background/50">
          <CardContent className="p-5 flex items-center justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Pending Requests</p>
              <p className="text-3xl font-extrabold text-amber-400 mt-1">{pendingCount}</p>
            </div>
            <div className="size-12 rounded-xl bg-amber-500/10 text-amber-400 flex items-center justify-center">
              <ClipboardList size={22} />
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border/60 gap-6">
        {([
          { key: 'users',    label: `User Directory (${users.length})`,         Icon: Users },
          { key: 'requests', label: `Permission Requests${pendingCount > 0 ? ` (${pendingCount})` : ''}`, Icon: ClipboardList },
          { key: 'activity', label: 'Audit & Activity',                          Icon: Activity },
        ] as const).map(({ key, label, Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key as Tab)}
            className={`pb-3 text-sm font-bold border-b-2 transition-all flex items-center gap-2 ${
              activeTab === key
                ? 'border-[#00a651] text-[#00a651]'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <Icon size={16} />
            {label}
            {key === 'requests' && pendingCount > 0 && (
              <span className="ml-1 size-5 rounded-full bg-amber-500 text-white text-[10px] font-extrabold flex items-center justify-center">
                {pendingCount}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* ── Tab 1: User Directory ── */}
      {activeTab === 'users' && (
        <Card className="glass-card border-border/40 bg-background/50">
          <CardHeader className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-border/40">
            <div>
              <CardTitle className="text-lg font-extrabold text-foreground">Authorized Staff Accounts</CardTitle>
              <CardDescription className="text-xs font-medium text-muted-foreground">
                Staff emails provisioned here can log in via Microsoft SSO.
              </CardDescription>
            </div>
            <div className="flex items-center gap-3 w-full sm:w-auto">
              <div className="relative flex-1 sm:w-64">
                <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Search email or role..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  className="pl-9 h-10 text-xs bg-background/80 rounded-xl"
                />
              </div>
              <Button size="icon" variant="outline" onClick={() => refetchUsers()} className="h-10 w-10 rounded-xl">
                <RefreshCw size={14} className={usersLoading ? 'animate-spin' : ''} />
              </Button>
            </div>
          </CardHeader>

          <CardContent className="p-0">
            {usersLoading ? (
              <div className="p-12 text-center text-muted-foreground text-sm font-medium">Loading user records...</div>
            ) : filteredUsers.length === 0 ? (
              <div className="p-12 text-center text-muted-foreground text-sm font-medium">No users found.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-muted/40 text-xs uppercase font-extrabold text-muted-foreground border-b border-border/40">
                    <tr>
                      <th className="px-6 py-3.5">User Email</th>
                      <th className="px-6 py-3.5">Primary Role</th>
                      <th className="px-6 py-3.5">All Portal Roles</th>
                      <th className="px-6 py-3.5">Status</th>
                      <th className="px-6 py-3.5">Joined</th>
                      <th className="px-6 py-3.5 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/30 font-medium">
                    {filteredUsers.map((u) => {
                      const badge = roleBadges[u.role] || { label: u.role, class: 'bg-muted text-muted-foreground' }
                      return (
                        <tr key={u.id} className="hover:bg-muted/30 transition-colors">
                          <td className="px-6 py-4">
                            <button
                              onClick={() => setActivityModal({ userId: u.id, email: u.email })}
                              className="flex items-center gap-3 group text-left"
                              title="View activity"
                            >
                              <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-[#0066b3]/10 text-[#0066b3] dark:text-[#00b2e3] font-bold text-xs">
                                {u.email.slice(0, 2).toUpperCase()}
                              </div>
                              <span className="font-bold text-foreground group-hover:text-[#00b2e3] transition-colors underline-offset-2 group-hover:underline">
                                {u.email}
                              </span>
                            </button>
                          </td>
                          <td className="px-6 py-4">
                            <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold border ${badge.class}`}>
                              {badge.label}
                            </span>
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex flex-wrap gap-1">
                              {(u.roles ?? []).slice(0, 4).map(r => {
                                const b = roleBadges[r] || { label: r, class: 'bg-muted text-muted-foreground' }
                                return (
                                  <span key={r} className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold border ${b.class}`}>
                                    {b.label}
                                  </span>
                                )
                              })}
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <span className="inline-flex items-center gap-1.5 text-xs font-bold text-[#00a651]">
                              <CheckCircle size={14} /> Active SSO
                            </span>
                          </td>
                          <td className="px-6 py-4 text-xs text-muted-foreground">
                            {u.created_at ? new Date(u.created_at).toLocaleDateString() : 'System Seed'}
                          </td>
                          <td className="px-6 py-4 text-right">
                            <div className="flex items-center justify-end gap-2">
                              <Button
                                size="icon"
                                variant="ghost"
                                onClick={() => setActivityModal({ userId: u.id, email: u.email })}
                                className="h-8 w-8 text-muted-foreground hover:bg-[#0066b3]/10 hover:text-[#00b2e3] rounded-lg"
                                title="View Activity"
                              >
                                <Eye size={14} />
                              </Button>
                              <Button
                                size="icon"
                                variant="ghost"
                                onClick={() => {
                                  if (confirm(`Revoke access for ${u.email}?`)) deleteMutation.mutate(u.id)
                                }}
                                className="h-8 w-8 text-destructive hover:bg-destructive/10 rounded-lg"
                                title="Revoke Access"
                              >
                                <Trash2 size={14} />
                              </Button>
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ── Tab 2: Permission Requests ── */}
      {activeTab === 'requests' && (
        <Card className="glass-card border-border/40 bg-background/50">
          <CardHeader className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 pb-4 border-b border-border/40">
            <div>
              <CardTitle className="text-lg font-extrabold text-foreground flex items-center gap-2">
                <ClipboardList className="text-amber-400" size={20} />
                Permission Requests
              </CardTitle>
              <CardDescription className="text-xs font-medium text-muted-foreground">
                Review and act on portal access requests from staff.
              </CardDescription>
            </div>
            <Button size="icon" variant="outline" onClick={() => refetchRequests()} className="h-10 w-10 rounded-xl">
              <RefreshCw size={14} className={requestsLoading ? 'animate-spin' : ''} />
            </Button>
          </CardHeader>

          <CardContent className="p-0">
            {requestsLoading ? (
              <div className="p-12 text-center text-muted-foreground text-sm">Loading requests...</div>
            ) : requests.length === 0 ? (
              <div className="p-12 text-center text-muted-foreground text-sm">No permission requests yet.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-muted/40 text-xs uppercase font-extrabold text-muted-foreground border-b border-border/40">
                    <tr>
                      <th className="px-6 py-3.5">Requester Email</th>
                      <th className="px-6 py-3.5">Requested Portals</th>
                      <th className="px-6 py-3.5">Reason</th>
                      <th className="px-6 py-3.5">Status</th>
                      <th className="px-6 py-3.5">Submitted</th>
                      <th className="px-6 py-3.5 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/30">
                    {requests.map((r) => {
                      const statusInfo = requestStatusBadge[r.status] || requestStatusBadge['PENDING']
                      const SIcon = statusInfo.Icon
                      return (
                        <tr key={r.id} className="hover:bg-muted/30 transition-colors">
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-3">
                              <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-amber-500/10 text-amber-400 font-bold text-xs">
                                {r.email.slice(0, 2).toUpperCase()}
                              </div>
                              <span className="font-bold text-foreground text-xs">{r.email}</span>
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex flex-wrap gap-1">
                              {r.requested_roles.map(role => {
                                const b = roleBadges[role] || { label: role, class: 'bg-muted text-muted-foreground' }
                                return (
                                  <span key={role} className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-bold border ${b.class}`}>
                                    {b.label}
                                  </span>
                                )
                              })}
                            </div>
                          </td>
                          <td className="px-6 py-4 text-xs text-muted-foreground max-w-[200px]">
                            {r.reason ? (
                              <span className="line-clamp-2">{r.reason}</span>
                            ) : (
                              <span className="italic">No reason provided</span>
                            )}
                            {r.rejection_note && (
                              <span className="block text-red-400 mt-1">Note: {r.rejection_note}</span>
                            )}
                          </td>
                          <td className="px-6 py-4">
                            <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold border ${statusInfo.class}`}>
                              <SIcon size={11} /> {statusInfo.label}
                            </span>
                          </td>
                          <td className="px-6 py-4 text-xs text-muted-foreground">
                            {new Date(r.created_at).toLocaleDateString()}
                          </td>
                          <td className="px-6 py-4 text-right">
                            {r.status === 'PENDING' && (
                              <div className="flex items-center justify-end gap-2">
                                <Button
                                  size="sm"
                                  onClick={() => approveMutation.mutate(r.id)}
                                  disabled={approveMutation.isPending}
                                  className="h-8 text-[11px] font-bold rounded-lg bg-gradient-to-r from-[#00a651] to-teal-600 text-white border-none"
                                >
                                  <CheckCircle2 size={12} className="mr-1" /> Approve
                                </Button>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => setRejectNoteModal({ id: r.id, email: r.email })}
                                  className="h-8 text-[11px] font-bold rounded-lg border-destructive/30 text-destructive hover:bg-destructive/10"
                                >
                                  <XCircle size={12} className="mr-1" /> Reject
                                </Button>
                              </div>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* ── Tab 3: Audit / Activity ── */}
      {activeTab === 'activity' && (
        <Card className="glass-card border-border/40 bg-background/50 p-6">
          <div className="flex items-center gap-3 text-foreground font-extrabold text-lg mb-2">
            <Activity className="text-[#00a651]" /> User Authentication Audit Trail
          </div>
          <p className="text-xs font-medium text-muted-foreground mb-6">
            Click any user's name in the User Directory to view their detailed role grant history.
          </p>
          <div className="space-y-3">
            {users.slice(0, 6).map((u, i) => (
              <button
                key={i}
                onClick={() => { setActivityModal({ userId: u.id, email: u.email }); setActiveTab('users') }}
                className="w-full flex items-center justify-between p-4 rounded-xl border border-border/40 bg-background/40 text-xs hover:bg-background/70 transition-colors"
              >
                <div className="flex items-center gap-3">
                  <div className="size-2 rounded-full bg-[#00a651] animate-pulse" />
                  <div className="text-left">
                    <span className="font-bold text-foreground">{u.email}</span>
                    <span className="text-muted-foreground block mt-0.5">
                      Roles: {(u.roles ?? [u.role]).join(', ')}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Eye size={12} />
                  <span>View Activity</span>
                </div>
              </button>
            ))}
          </div>
        </Card>
      )}

      {/* ── Add User Modal ── */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md glass-card rounded-2xl p-6 bg-background border border-border/60 shadow-2xl space-y-5">
            <div className="flex items-center justify-between border-b border-border/40 pb-4">
              <h2 className="text-xl font-extrabold text-foreground flex items-center gap-2">
                <UserPlus className="text-[#00a651]" size={20} /> Provision New Staff Account
              </h2>
              <button onClick={() => { setShowAddModal(false); setSelectedRoles(['GMF_HANDLER']) }} className="text-muted-foreground hover:text-foreground font-bold">
                <X size={18} />
              </button>
            </div>
            <form onSubmit={handleCreateUser} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email" className="text-xs font-bold text-foreground">Staff Email Address</Label>
                <div className="relative">
                  <Mail size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    id="email"
                    placeholder="john or john@slt.com.lk"
                    value={emailInput}
                    onChange={(e) => setEmailInput(e.target.value)}
                    required
                    className="pl-9 h-11 text-xs rounded-xl"
                  />
                </div>
                <p className="text-[11px] text-muted-foreground font-medium">
                  If suffix is omitted, <code className="text-[#00a651]">@slt.com.lk</code> will be appended automatically.
                </p>
              </div>

              {/* ── Multi-Portal Checkbox Group ── */}
              <div className="space-y-2">
                <Label className="text-xs font-bold text-foreground">Portal Access</Label>
                <p className="text-[11px] text-muted-foreground font-medium -mt-1">Tick one or more portals to grant access to.</p>
                <div className="space-y-2 pt-1">
                  {PORTAL_OPTIONS.map((portal) => {
                    const isChecked = selectedRoles.includes(portal.value)
                    return (
                      <label
                        key={portal.value}
                        className={`flex items-center gap-3 p-3 rounded-xl border cursor-pointer transition-all select-none ${
                          isChecked
                            ? `${portal.borderColor} ${portal.bg}`
                            : 'border-border/40 hover:border-border/70 hover:bg-muted/20'
                        }`}
                      >
                        <div
                          className={`w-4 h-4 rounded flex items-center justify-center border-2 shrink-0 transition-all ${
                            isChecked
                              ? 'bg-[#00a651] border-[#00a651]'
                              : 'border-border bg-background'
                          }`}
                          onClick={() => {
                            setSelectedRoles(prev =>
                              prev.includes(portal.value)
                                ? prev.filter(r => r !== portal.value)
                                : [...prev, portal.value]
                            )
                          }}
                        >
                          {isChecked && (
                            <svg viewBox="0 0 10 8" className="w-2.5 h-2.5" fill="none">
                              <path d="M1 4L3.5 6.5L9 1" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                            </svg>
                          )}
                        </div>
                        <input
                          type="checkbox"
                          className="sr-only"
                          checked={isChecked}
                          onChange={() => {
                            setSelectedRoles(prev =>
                              prev.includes(portal.value)
                                ? prev.filter(r => r !== portal.value)
                                : [...prev, portal.value]
                            )
                          }}
                        />
                        <span className={`text-xs font-bold ${isChecked ? portal.color : 'text-muted-foreground'}`}>
                          {portal.label}
                        </span>
                      </label>
                    )
                  })}
                </div>
                {selectedRoles.length === 0 && (
                  <p className="text-[11px] text-red-400 font-medium">⚠ Please select at least one portal.</p>
                )}
              </div>

              <div className="pt-4 flex justify-end gap-3 border-t border-border/40">
                <Button type="button" variant="outline" onClick={() => { setShowAddModal(false); setSelectedRoles(['GMF_HANDLER']) }} className="h-10 rounded-xl text-xs font-bold">
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={createMutation.isPending || selectedRoles.length === 0}
                  className="h-10 rounded-xl bg-gradient-to-r from-[#00a651] to-teal-600 text-white font-extrabold text-xs shadow-md border-none"
                >
                  {createMutation.isPending ? 'Saving...' : `Provision User${selectedRoles.length > 1 ? ` (${selectedRoles.length} Portals)` : ''}`}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* ── Reject Note Modal ── */}
      {rejectNoteModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-sm glass-card rounded-2xl p-6 bg-background border border-border/60 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-border/40 pb-3">
              <h2 className="text-lg font-extrabold text-foreground flex items-center gap-2">
                <XCircle className="text-destructive" size={18} /> Reject Request
              </h2>
              <button onClick={() => setRejectNoteModal(null)} className="text-muted-foreground hover:text-foreground">
                <X size={16} />
              </button>
            </div>
            <p className="text-xs text-muted-foreground font-medium">
              Rejecting access request from <span className="text-foreground font-bold">{rejectNoteModal.email}</span>.
            </p>
            <div className="space-y-2">
              <Label className="text-xs font-bold text-foreground">Rejection Reason <span className="font-normal text-muted-foreground">(optional)</span></Label>
              <textarea
                rows={3}
                placeholder="Provide a reason for rejection..."
                value={rejectNote}
                onChange={(e) => setRejectNote(e.target.value)}
                className="w-full rounded-xl border border-border bg-background px-3 py-2 text-xs font-medium text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-destructive resize-none"
              />
            </div>
            <div className="flex justify-end gap-3 pt-2">
              <Button variant="outline" onClick={() => setRejectNoteModal(null)} className="h-9 rounded-xl text-xs font-bold">Cancel</Button>
              <Button
                onClick={() => rejectMutation.mutate({ id: rejectNoteModal.id, note: rejectNote || undefined })}
                disabled={rejectMutation.isPending}
                className="h-9 rounded-xl text-xs font-bold bg-destructive text-white border-none hover:bg-destructive/90"
              >
                {rejectMutation.isPending ? 'Rejecting...' : 'Confirm Reject'}
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ── User Activity Modal ── */}
      {activityModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-lg glass-card rounded-2xl bg-background border border-border/60 shadow-2xl overflow-hidden">
            <div className="p-5 border-b border-border/40 flex items-center justify-between">
              <div>
                <h2 className="text-lg font-extrabold text-foreground flex items-center gap-2">
                  <Activity className="text-[#00a651]" size={18} />
                  User Activity
                </h2>
                <p className="text-xs text-muted-foreground font-medium mt-0.5">{activityModal.email}</p>
              </div>
              <button onClick={() => setActivityModal(null)} className="text-muted-foreground hover:text-foreground">
                <X size={18} />
              </button>
            </div>
            <div className="p-5 space-y-5 max-h-[70vh] overflow-y-auto">
              {!activity ? (
                <div className="text-center text-sm text-muted-foreground py-8">Loading activity...</div>
              ) : (
                <>
                  {/* Role Grants */}
                  <div>
                    <p className="text-xs font-extrabold uppercase tracking-wider text-muted-foreground mb-3">
                      Portal Role Grants
                    </p>
                    {activity.role_grants.length === 0 ? (
                      <p className="text-xs text-muted-foreground italic">No role grants found.</p>
                    ) : (
                      <div className="space-y-2">
                        {activity.role_grants.map((g, i) => {
                          const b = roleBadges[g.role] || { label: g.role, class: 'bg-muted text-muted-foreground' }
                          return (
                            <div key={i} className="flex items-center justify-between p-3 rounded-xl border border-border/40 bg-background/50">
                              <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold border ${b.class}`}>
                                {b.label}
                              </span>
                              <span className="text-xs text-muted-foreground font-mono">
                                {new Date(g.granted_at).toLocaleString()}
                              </span>
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>

                  {/* Approved Requests */}
                  {activity.approved_requests.length > 0 && (
                    <div>
                      <p className="text-xs font-extrabold uppercase tracking-wider text-muted-foreground mb-3">
                        Approved Access Requests
                      </p>
                      <div className="space-y-2">
                        {activity.approved_requests.map((r, i) => (
                          <div key={i} className="p-3 rounded-xl border border-[#00a651]/30 bg-[#00a651]/5 text-xs space-y-1">
                            <div className="flex flex-wrap gap-1">
                              {r.requested_roles.map(role => {
                                const b = roleBadges[role] || { label: role, class: 'bg-muted text-muted-foreground' }
                                return (
                                  <span key={role} className={`inline-flex items-center px-2 py-0.5 rounded-full font-bold border ${b.class} text-[10px]`}>
                                    {b.label}
                                  </span>
                                )
                              })}
                            </div>
                            {r.reason && <p className="text-muted-foreground italic">"{r.reason}"</p>}
                            <p className="text-muted-foreground">Approved: {r.approved_at ? new Date(r.approved_at).toLocaleString() : '—'}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
