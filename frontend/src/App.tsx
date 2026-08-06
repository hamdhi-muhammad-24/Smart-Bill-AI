import { Route, Routes } from 'react-router-dom'
import { Toaster } from '@/components/ui/sonner'
import RequireRole from './auth/RequireRole'
import AdminLayout from './components/AdminLayout'
import Admin1Layout from './components/Admin1Layout'
import Login from './pages/Login'
import NotFound from './pages/NotFound'
import PublicPortal from './pages/PublicPortal'
import Dashboard from './pages/admin/Dashboard'
import GmfMonitor from './pages/admin/GmfMonitor'
import InvoicePreview from './pages/admin/InvoicePreview'
import GenerationHub from './pages/admin/GenerationHub'
import OutputArchive from './pages/admin/OutputArchive'
import ActivityLog from './pages/admin/ActivityLog'
import InvoiceTemplates from './pages/admin/InvoiceTemplates'
import Admin1Dashboard from './pages/admin/Admin1Dashboard'
import UploadCenter from './pages/admin/UploadCenter'
import ManagerLayout from './components/ManagerLayout'
import ManagerDashboard from './pages/admin/ManagerDashboard'
import EnvelopeLayout from './components/EnvelopeLayout'
import EnvelopeDashboard from './pages/envelope/EnvelopeDashboard'
import EnvelopeManager from './pages/envelope/EnvelopeManager'
import { ThemeProvider } from './components/ThemeProvider'

export default function App() {
  return (
    <ThemeProvider defaultTheme="system" storageKey="slt-billing-theme">
      <Routes>
        <Route index element={<PublicPortal />} />
        <Route path="/login" element={<Login />} />

        {/* System Administration Console */}
        <Route element={<RequireRole role="admin" />}>
          <Route path="/admin" element={<AdminLayout />}>
            <Route index element={<Dashboard />} />
            <Route path="gmf-monitor" element={<GmfMonitor />} />
            <Route path="invoice-preview" element={<InvoicePreview />} />
            <Route path="generation-hub" element={<GenerationHub />} />
            <Route path="output-archive" element={<OutputArchive />} />
            <Route path="activity-log" element={<ActivityLog />} />
            <Route path="invoice-templates" element={<InvoiceTemplates />} />
          </Route>
        </Route>

        {/* GMF Handler Operations Portal */}
        <Route element={<RequireRole role="gmf_handler" />}>
          <Route path="/gmf-handler" element={<Admin1Layout />}>
            <Route index element={<Admin1Dashboard />} />
            <Route path="gmf-monitor" element={<GmfMonitor />} />
            <Route path="upload-center" element={<UploadCenter />} />
          </Route>
        </Route>

        {/* Envelope Handler Operations Portal */}
        <Route element={<RequireRole role="envelope_handler" />}>
          <Route path="/envelope-handler" element={<EnvelopeLayout />}>
            <Route index element={<EnvelopeDashboard />} />
            <Route path="manager" element={<EnvelopeManager />} />
          </Route>
        </Route>

        {/* User Management Portal */}
        <Route element={<RequireRole role="manager" />}>
          <Route path="/manager" element={<ManagerLayout />}>
            <Route index element={<ManagerDashboard />} />
          </Route>
        </Route>

        <Route path="*" element={<NotFound />} />
      </Routes>

      <Toaster />
    </ThemeProvider>
  )
}
