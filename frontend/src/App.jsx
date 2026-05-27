import React, { useState, useCallback } from 'react'
import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom'
import axios from 'axios'
import Dashboard from './pages/Dashboard'
import Pipeline from './pages/Pipeline'
import { LayoutDashboard, Columns4, Zap, Menu, X } from 'lucide-react'

const API_BASE_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000'

function NavLink({ to, icon: Icon, label, badge, onClick }) {
  const location = useLocation()
  const isActive = location.pathname === to
  return (
    <Link
      to={to}
      id={`nav-${label.toLowerCase()}`}
      onClick={onClick}
      className="flex items-center justify-between px-4 py-3 rounded-lg text-[15px] font-medium transition-colors duration-150"
      style={{
        color: isActive ? '#2563eb' : '#475569',
        background: isActive ? '#eff6ff' : 'transparent',
      }}
      onMouseOver={e => { if (!isActive) e.currentTarget.style.background = '#f8fafc' }}
      onMouseOut={e => { if (!isActive) e.currentTarget.style.background = 'transparent' }}
    >
      <span className="flex items-center gap-3">
        <Icon size={20} style={{ color: isActive ? '#2563eb' : '#94a3b8' }} />
        {label}
      </span>
      {badge > 0 && (
        <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-red-100 text-red-600">
          {badge}
        </span>
      )}
    </Link>
  )
}

function Sidebar({ open, onClose, analytics }) {
  return (
    <>
      {/* Mobile overlay */}
      {open && (
        <div
          className="fixed inset-0 z-20 bg-black/30 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar panel */}
      <aside
        className={`
          fixed top-0 left-0 z-30 h-full flex flex-col
          transition-transform duration-300 ease-in-out
          lg:static lg:translate-x-0 lg:z-auto
          ${open ? 'translate-x-0' : '-translate-x-full'}
        `}
        style={{ width: '260px', background: '#ffffff', borderRight: '1px solid #e2e8f0', flexShrink: 0 }}
      >
        {/* Logo */}
        <div className="px-5 py-5 flex items-center justify-between" style={{ borderBottom: '1px solid #f1f5f9' }}>
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg flex items-center justify-center bg-blue-600">
              <Zap size={18} className="text-white" />
            </div>
            <span className="font-bold text-slate-900 text-xl">SocialPipe</span>
          </div>
          <button onClick={onClose} className="lg:hidden text-slate-400 hover:text-slate-600 p-1">
            <X size={20} />
          </button>
        </div>

        {/* Nav */}
        <div className="flex-1 px-3 py-5 space-y-1 overflow-y-auto">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest px-4 mb-3">Menu</p>
          <NavLink to="/" icon={LayoutDashboard} label="Dashboard" onClick={onClose} />
          <NavLink to="/pipeline" icon={Columns4} label="Pipeline" badge={analytics.hot_count} onClick={onClose} />
        </div>

        {/* Footer */}
        <div className="p-4" style={{ borderTop: '1px solid #f1f5f9' }}>
          <div className="px-3 py-2 rounded-lg bg-slate-50">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-widest">Hackathon 2026</p>
            <p className="text-sm text-slate-600 mt-0.5 font-medium">Philippines Edition</p>
          </div>
        </div>
      </aside>
    </>
  )
}

function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [leads, setLeads] = useState([])
  const [analytics, setAnalytics] = useState({ total_leads: 0, hot_count: 0, warm_count: 0, pushed_count: 0 })

  const refreshLeads = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE_URL}/api/leads`)
      setLeads(res.data)
    } catch (e) { console.error(e) }
  }, [])

  const refreshAnalytics = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE_URL}/api/analytics`)
      const d = res.data
      setAnalytics({
        total_leads: d.total_leads || 0,
        hot_count: d.hot_count || 0,
        warm_count: d.warm_count || 0,
        pushed_count: d.in_pipeline_count || 0,
      })
    } catch (e) { console.error(e) }
  }, [])

  const refreshAll = useCallback(() => {
    refreshLeads()
    refreshAnalytics()
  }, [refreshLeads, refreshAnalytics])

  return (
    <Router>
      <div className="flex h-screen w-screen overflow-hidden" style={{ background: '#f8fafc' }}>

        <Sidebar open={sidebarOpen} onClose={() => setSidebarOpen(false)} analytics={analytics} />

        {/* ── Main content ── */}
        <div className="flex flex-col flex-1 min-w-0 overflow-hidden">

          {/* Top bar */}
          <header
            className="shrink-0 h-14 flex items-center gap-4 px-4 sm:px-6"
            style={{ background: '#ffffff', borderBottom: '1px solid #e2e8f0' }}
          >
            {/* Hamburger (mobile only) */}
            <button
              id="sidebar-toggle"
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-2 rounded-lg text-slate-500 hover:bg-slate-100 transition-colors"
            >
              <Menu size={22} />
            </button>

            <span className="text-sm sm:text-base text-slate-500 flex-1 min-w-0 truncate">
              Welcome back, <span className="font-semibold text-slate-800">Sales Agent</span>
            </span>

            <div className="flex items-center gap-3 shrink-0">
              {analytics.hot_count > 0 && (
                <span className="hidden sm:inline-flex text-xs font-semibold px-3 py-1.5 rounded-lg bg-red-50 text-red-600 border border-red-100 whitespace-nowrap">
                  🔥 {analytics.hot_count} hot lead{analytics.hot_count > 1 ? 's' : ''}
                </span>
              )}
              <div className="w-9 h-9 rounded-full bg-blue-600 flex items-center justify-center text-sm font-bold text-white shrink-0">
                SA
              </div>
            </div>
          </header>

          {/* Page */}
          <main className="flex-1 overflow-auto w-full">
            <Routes>
              <Route path="/" element={<Dashboard leads={leads} setLeads={setLeads} analytics={analytics} refreshAll={refreshAll} />} />
              <Route path="/pipeline" element={<Pipeline leads={leads} refreshAll={refreshAll} />} />
            </Routes>
          </main>
        </div>

      </div>
    </Router>
  )
}

export default App
