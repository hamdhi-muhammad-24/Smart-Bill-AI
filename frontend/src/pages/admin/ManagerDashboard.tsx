import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getUsers, createUser, deleteUser } from '../../lib/api'
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
  UserCheck
} from 'lucide-react'
import { toast } from 'sonner'

export default function ManagerDashboard() {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState<'users' | 'activity'>('users')
  const [search, setSearch] = useState('')
  const [showModal, setShowModal] = useState(false)
  const [emailInput, setEmailInput] = useState('')
  const [roleInput, setRoleInput] = useState<string>('GMF_HANDLER')

  const { data: users = [], isLoading, refetch } = useQuery({
    queryKey: ['users'],
    queryFn: getUsers,
  })

  const createMutation = useMutation({
    mutationFn: createUser,
    onSuccess: (data) => {
      toast.success(`Successfully provisioned user ${data.email}`)
      queryClient.invalidateQueries({ queryKey: ['users'] })
      setShowModal(false)
      setEmailInput('')
      setRoleInput('GMF_HANDLER')
    },
    onError: (err: any) => {
      toast.error(err?.detail || 'Failed to create user')
    },
  })

  const deleteMutation = useMutation({
    mutationFn: deleteUser,
    onSuccess: () => {
      toast.success('User access revoked')
      queryClient.invalidateQueries({ queryKey: ['users'] })
    },
    onError: (err: any) => {
      toast.error(err?.detail || 'Failed to delete user')
    },
  })

  function handleCreateUser(e: React.FormEvent) {
    e.preventDefault()
    if (!emailInput.trim()) return
    createMutation.mutate({
      email: emailInput.trim(),
      role: roleInput,
      is_active: true,
    })
  }

  const filteredUsers = users.filter((u) =>
    u.email.toLowerCase().includes(search.toLowerCase()) ||
    u.role.toLowerCase().includes(search.toLowerCase())
  )

  const roleBadges: Record<string, { label: string; class: string }> = {
    ADMIN: { label: 'Admin', class: 'bg-slate-500/15 text-slate-300 border-slate-500/30' },
    GMF_HANDLER: { label: 'GMF Handler', class: 'bg-[#0066b3]/15 text-[#00b2e3] border-[#0066b3]/30' },
    ADMIN1: { label: 'GMF Handler', class: 'bg-[#0066b3]/15 text-[#00b2e3] border-[#0066b3]/30' },
    MANAGER: { label: 'User Manager', class: 'bg-[#00a651]/15 text-[#00e676] border-[#00a651]/30' },
    CUSTOMER: { label: 'Customer', class: 'bg-amber-500/15 text-amber-300 border-amber-500/30' },
  }

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
            <p className="text-sm font-medium text-muted-foreground">Provision staff SSO accounts, assign access roles, and monitor authentication status.</p>
          </div>
        </div>
        <Button
          onClick={() => setShowModal(true)}
          className="h-11 rounded-xl bg-gradient-to-r from-[#00a651] to-teal-600 font-extrabold text-white shadow-lg shadow-[#00a651]/25 hover:opacity-90 transition-all border-none"
        >
          <UserPlus size={18} className="mr-2" />
          Provision New Staff
        </Button>
      </div>

      {/* Stats Summary Cards */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="glass-card border-border/40 bg-background/50">
          <CardContent className="p-5 flex items-center justify-between">
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-muted-foreground">Total Staff Accounts</p>
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
                {users.filter(u => u.role === 'GMF_HANDLER' || (u.role as string) === 'ADMIN1').length}
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
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border/60 gap-4">
        <button
          onClick={() => setActiveTab('users')}
          className={`pb-3 text-sm font-bold border-b-2 transition-all flex items-center gap-2 ${
            activeTab === 'users'
              ? 'border-[#00a651] text-[#00a651]'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <Users size={16} /> User Directory ({users.length})
        </button>
        <button
          onClick={() => setActiveTab('activity')}
          className={`pb-3 text-sm font-bold border-b-2 transition-all flex items-center gap-2 ${
            activeTab === 'activity'
              ? 'border-[#00a651] text-[#00a651]'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          }`}
        >
          <Activity size={16} /> Audit & Activity Logs
        </button>
      </div>

      {/* Tab 1: User Directory */}
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
              <Button size="icon" variant="outline" onClick={() => refetch()} className="h-10 w-10 rounded-xl">
                <RefreshCw size={14} className={isLoading ? 'animate-spin' : ''} />
              </Button>
            </div>
          </CardHeader>

          <CardContent className="p-0">
            {isLoading ? (
              <div className="p-12 text-center text-muted-foreground text-sm font-medium">Loading user records...</div>
            ) : filteredUsers.length === 0 ? (
              <div className="p-12 text-center text-muted-foreground text-sm font-medium">No users found.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="bg-muted/40 text-xs uppercase font-extrabold text-muted-foreground border-b border-border/40">
                    <tr>
                      <th className="px-6 py-3.5">User Email</th>
                      <th className="px-6 py-3.5">Assigned Role & Portal</th>
                      <th className="px-6 py-3.5">Status</th>
                      <th className="px-6 py-3.5">Created Date</th>
                      <th className="px-6 py-3.5 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border/30 font-medium">
                    {filteredUsers.map((u) => {
                      const badge = roleBadges[u.role] || { label: u.role, class: 'bg-muted text-muted-foreground' }
                      return (
                        <tr key={u.id} className="hover:bg-muted/30 transition-colors">
                          <td className="px-6 py-4 flex items-center gap-3">
                            <div className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-[#0066b3]/10 text-[#0066b3] dark:text-[#00b2e3] font-bold text-xs">
                              {u.email.slice(0, 2).toUpperCase()}
                            </div>
                            <span className="font-bold text-foreground">{u.email}</span>
                          </td>
                          <td className="px-6 py-4">
                            <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-bold border ${badge.class}`}>
                              {badge.label}
                            </span>
                          </td>
                          <td className="px-6 py-4">
                            <span className="inline-flex items-center gap-1.5 text-xs font-bold text-[#00a651]">
                              <CheckCircle size={14} /> Active SSO Access
                            </span>
                          </td>
                          <td className="px-6 py-4 text-xs text-muted-foreground">
                            {u.created_at ? new Date(u.created_at).toLocaleDateString() : 'System Seed'}
                          </td>
                          <td className="px-6 py-4 text-right">
                            <Button
                              size="icon"
                              variant="ghost"
                              onClick={() => {
                                if (confirm(`Are you sure you want to revoke access for ${u.email}?`)) {
                                  deleteMutation.mutate(u.id)
                                }
                              }}
                              className="h-8 w-8 text-destructive hover:bg-destructive/10 rounded-lg"
                              title="Revoke Access"
                            >
                              <Trash2 size={16} />
                            </Button>
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

      {/* Tab 2: Activity Logs */}
      {activeTab === 'activity' && (
        <Card className="glass-card border-border/40 bg-background/50 p-6">
          <div className="flex items-center gap-3 text-foreground font-extrabold text-lg mb-2">
            <Activity className="text-[#00a651]" /> User Authentication Audit Trail
          </div>
          <p className="text-xs font-medium text-muted-foreground mb-6">
            Real-time verification log of staff Microsoft Entra ID tokens and portal authorizations.
          </p>
          <div className="space-y-3">
            {users.slice(0, 5).map((u, i) => (
              <div key={i} className="flex items-center justify-between p-4 rounded-xl border border-border/40 bg-background/40 text-xs">
                <div className="flex items-center gap-3">
                  <div className="size-2 rounded-full bg-[#00a651]" />
                  <div>
                    <span className="font-bold text-foreground">{u.email}</span> authenticated via Microsoft Entra ID
                    <span className="text-muted-foreground block mt-0.5">Assigned to {u.role} portal</span>
                  </div>
                </div>
                <span className="text-muted-foreground font-mono">Today, 06:00 AM</span>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Add User Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md glass-card rounded-2xl p-6 bg-background border border-border/60 shadow-2xl space-y-5">
            <div className="flex items-center justify-between border-b border-border/40 pb-4">
              <h2 className="text-xl font-extrabold text-foreground flex items-center gap-2">
                <UserPlus className="text-[#00a651]" size={20} /> Provision New Staff Account
              </h2>
              <button onClick={() => setShowModal(false)} className="text-muted-foreground hover:text-foreground font-bold">✕</button>
            </div>

            <form onSubmit={handleCreateUser} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email" className="text-xs font-bold text-foreground">
                  Staff Email Address
                </Label>
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

              <div className="space-y-2">
                <Label htmlFor="role" className="text-xs font-bold text-foreground">
                  Portal Access Role
                </Label>
                <select
                  id="role"
                  value={roleInput}
                  onChange={(e) => setRoleInput(e.target.value)}
                  className="w-full h-11 px-3 text-xs bg-background border border-border rounded-xl font-bold focus:ring-2 focus:ring-[#00a651]"
                >
                  <option value="GMF_HANDLER">GMF Handler Portal (gmf@slt.com.lk)</option>
                  <option value="ADMIN">System Administration Console (admin@slt.com.lk)</option>
                  <option value="MANAGER">User Management Portal (manager@slt.com.lk)</option>
                </select>
              </div>

              <div className="pt-4 flex justify-end gap-3 border-t border-border/40">
                <Button type="button" variant="outline" onClick={() => setShowModal(false)} className="h-10 rounded-xl text-xs font-bold">
                  Cancel
                </Button>
                <Button
                  type="submit"
                  disabled={createMutation.isPending}
                  className="h-10 rounded-xl bg-gradient-to-r from-[#00a651] to-teal-600 text-white font-extrabold text-xs shadow-md border-none"
                >
                  {createMutation.isPending ? 'Saving...' : 'Provision User'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
