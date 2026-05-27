import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  Users, Flame, Thermometer, Send,
  Search, Activity, ChevronRight, ExternalLink, Zap,
} from 'lucide-react';

const RAW_API_BASE_URL = (import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000').trim();
const API_BASE_URL = RAW_API_BASE_URL.replace(/\/+$/, '').replace(/\/api$/, '');

/* ── Helpers ─────────────────────────────────────────── */
const SCORE_META = {
  hot:  { label: 'HOT',  bg: '#fef2f2', color: '#dc2626', border: '#fecaca', dot: '#ef4444' },
  warm: { label: 'WARM', bg: '#fff7ed', color: '#ea580c', border: '#fed7aa', dot: '#f97316' },
  cold: { label: 'COLD', bg: '#eff6ff', color: '#2563eb', border: '#bfdbfe', dot: '#3b82f6' },
  none: { label: '—',    bg: '#f8fafc', color: '#94a3b8', border: '#e2e8f0', dot: '#cbd5e1' },
};

const getLevel = (score) => {
  if (score >= 90) return SCORE_META.hot;
  if (score >= 70) return SCORE_META.warm;
  if (score >= 50) return SCORE_META.cold;
  return SCORE_META.none;
};

const SIGNAL_LABELS = {
  product_request:   'Product Request',
  competitor_pain:   'Competitor Pain',
  active_evaluation: 'Active Evaluation',
  advice_seeking:    'Advice Seeking',
  urgent_need:       'Urgent Need',
  no_signal:         'No Signal',
};

/* ── KPI Card ────────────────────────────────────────── */
function KpiCard({ label, value, icon: Icon, accent }) {
  return (
    <div
      id={`kpi-${label.toLowerCase().replace(/\s/g, '-')}`}
      className="bg-white rounded-xl p-5 flex items-center gap-4 w-full"
      style={{ border: '1px solid #e2e8f0' }}
    >
      <div
        className="w-12 h-12 rounded-xl flex items-center justify-center shrink-0"
        style={{ background: `${accent}18` }}
      >
        <Icon size={24} style={{ color: accent }} />
      </div>
      <div className="min-w-0">
        <p className="text-xs sm:text-sm font-medium text-slate-500 truncate">{label}</p>
        <p className="text-3xl sm:text-4xl font-bold text-slate-900 leading-tight">{value}</p>
      </div>
    </div>
  );
}

/* ── Lead Feed Card ──────────────────────────────────── */
function LeadFeedCard({ lead }) {
  const sourceUrl = lead.source_url || lead.url;
  const lvl = getLevel(lead.score ?? 0);
  const signal = SIGNAL_LABELS[lead.signal_type] || lead.signal_type || '—';
  const tsLabel = lead.timestamp ? new Date(Number(lead.timestamp) * 1000).toLocaleString() : null;
  const primaryText = lead.content || lead.pain_point || '—';

  return (
    <div
      className="bg-white rounded-xl p-4 sm:p-5 transition-shadow hover:shadow-sm w-full"
      style={{ border: '1px solid #e2e8f0' }}
    >
      <div className="flex items-center justify-between mb-2.5">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
          {lead.platform || 'Reddit'}
        </span>
        <span
          className="inline-flex items-center gap-1.5 text-xs font-bold px-2.5 py-1 rounded-full"
          style={{ background: lvl.bg, color: lvl.color, border: `1px solid ${lvl.border}` }}
        >
          <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: lvl.dot }}></span>
          {lvl.label} {lead.score > 0 ? `· ${lead.score}` : ''}
        </span>
      </div>

      <p className="text-sm font-semibold text-blue-600 mb-1.5">{signal}</p>

      {(lead.author || tsLabel) && (
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-400 mb-2">
          {lead.author && <span className="truncate">u/{lead.author}</span>}
          {lead.author && tsLabel && <span>•</span>}
          {tsLabel && <span className="truncate">{tsLabel}</span>}
        </div>
      )}

      <p className="text-sm text-slate-600 line-clamp-3 leading-relaxed mb-3 whitespace-pre-wrap">
        {primaryText}
      </p>

      {lead.analysis_error && (
        <p className="text-xs text-rose-500 mb-3 line-clamp-2">
          AI: {lead.analysis_error}
        </p>
      )}

      {sourceUrl ? (
        <a
          href={sourceUrl}
          target="_blank"
          rel="noreferrer"
          id={`lead-view-${lead.id}`}
          className="flex items-center justify-center gap-2 w-full py-2.5 rounded-lg text-sm font-semibold text-blue-600 transition-colors hover:bg-blue-50"
          style={{ border: '1px solid #bfdbfe' }}
        >
          View Post <ExternalLink size={14} />
        </a>
      ) : (
        <div
          className="flex items-center justify-center w-full py-2.5 rounded-lg text-sm text-slate-300 cursor-not-allowed"
          style={{ border: '1px dashed #e2e8f0' }}
        >
          No source link
        </div>
      )}
    </div>
  );
}

/* ── Dashboard ───────────────────────────────────────── */
const Dashboard = () => {
  const [keywords, setKeywords]     = useState('');
  const [isScanning, setIsScanning] = useState(false);
  const [logs, setLogs]             = useState([]);
  const [leads, setLeads]           = useState([]);
  const [analytics, setAnalytics]   = useState({ total_leads: 0, hot_count: 0, warm_count: 0, pushed_count: 0 });

  useEffect(() => { fetchAnalytics(); fetchRecentLeads(); }, []);

  const fetchAnalytics = async () => {
    try {
      const r = await axios.get(`${API_BASE_URL}/api/analytics`);
      const d = r.data;
      setAnalytics({
        total_leads:  d.total_leads || 0,
        hot_count:    d.hot_count || 0,
        warm_count:   d.warm_count || 0,
        pushed_count: d.in_pipeline_count || 0,
      });
    } catch (e) { console.error(e); }
  };

  const fetchRecentLeads = async () => {
    try {
      const r = await axios.get(`${API_BASE_URL}/api/leads`);
      setLeads(r.data.slice(0, 10));
    } catch (e) { console.error(e); }
  };

  const runScan = async () => {
    if (!keywords.trim()) return;
    const kwList = keywords.split(',').map(k => k.trim()).filter(Boolean);
    setIsScanning(true);
    setLogs([]);
    kwList.forEach((kw, i) =>
      setTimeout(() => setLogs(p => [...p, `Scanning for: "${kw}"…`]), i * 800)
    );
    try {
      const r = await axios.post(`${API_BASE_URL}/api/scan`, { keywords: kwList });
      setTimeout(() => {
        setLogs(p => [...p, `✓ Found ${r.data.length} leads — scoring complete.`]);
        setLeads(p => [...r.data, ...p].slice(0, 10));
        fetchAnalytics();
        setIsScanning(false);
      }, kwList.length * 800 + 500);
    } catch (e) {
      setLogs(p => [...p, `✗ Error: ${e.message}`]);
      setIsScanning(false);
    }
  };

  const kpis = [
    { label: 'Total Leads', value: analytics.total_leads, icon: Users,       accent: '#6366f1' },
    { label: 'Hot Leads',   value: analytics.hot_count,   icon: Flame,       accent: '#ef4444' },
    { label: 'Warm Leads',  value: analytics.warm_count,  icon: Thermometer, accent: '#f97316' },
    { label: 'In Pipeline', value: analytics.pushed_count, icon: Send,       accent: '#10b981' },
  ];

  return (
    <div className="p-4 sm:p-6 lg:p-8 space-y-6 w-full" style={{ background: '#f8fafc', minHeight: '100%' }}>

      {/* Page title */}
      <div>
        <h1 className="text-xl sm:text-2xl font-bold text-slate-900">Dashboard</h1>
        <p className="text-sm sm:text-base text-slate-500 mt-1">Scan social channels and capture high-intent buyers.</p>
      </div>

      {/* KPIs — 1 col → 2 col → 4 col */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-4 w-full">
        {kpis.map((k, i) => <KpiCard key={i} {...k} />)}
      </div>

      {/* Body — stacks on mobile, 2-col on lg+ */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 w-full">

        {/* Scanner + Log — takes 2/3 on large */}
        <div className="lg:col-span-2 space-y-5 min-w-0">

          {/* Keyword Input */}
          <div className="bg-white rounded-xl p-5 sm:p-6 w-full" style={{ border: '1px solid #e2e8f0' }}>
            <div className="flex items-center gap-2 mb-4">
              <Zap size={18} className="text-blue-600 shrink-0" />
              <h2 className="text-sm sm:text-base font-semibold text-slate-800">Target Keywords</h2>
              <span className="ml-auto text-xs sm:text-sm text-slate-400 shrink-0">Comma-separated</span>
            </div>

            <div className="space-y-3">
              <div className="relative">
                <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                <input
                  id="keyword-input"
                  type="text"
                  placeholder="e.g. need CRM, voice AI, sales software..."
                  className="w-full pl-10 pr-4 py-3 sm:py-3.5 text-sm sm:text-base rounded-lg outline-none transition-all placeholder:text-slate-300"
                  style={{ border: '1px solid #e2e8f0', background: '#f8fafc', color: '#0f172a' }}
                  onFocus={e => e.target.style.borderColor = '#93c5fd'}
                  onBlur={e => e.target.style.borderColor = '#e2e8f0'}
                  value={keywords}
                  onChange={e => setKeywords(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && !isScanning && runScan()}
                  disabled={isScanning}
                />
              </div>

              <button
                id="run-scan-btn"
                onClick={runScan}
                disabled={isScanning || !keywords.trim()}
                className="w-full py-3 sm:py-3.5 rounded-lg text-sm sm:text-base font-semibold text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors flex items-center justify-center gap-2"
              >
                {isScanning ? (
                  <>
                    <div className="w-4 h-4 sm:w-5 sm:h-5 rounded-full border-2 border-white/30 border-t-white spin" />
                    Scanning…
                  </>
                ) : (
                  <>
                    <Activity size={16} />
                    Run Scan
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Activity Log */}
          <div className="bg-white rounded-xl p-5 sm:p-6 w-full" style={{ border: '1px solid #e2e8f0' }}>
            <div className="flex items-center gap-2 mb-4">
              <h3 className="text-sm sm:text-base font-semibold text-slate-800">Activity Log</h3>
              {isScanning && (
                <span className="ml-auto flex items-center gap-1.5 text-xs sm:text-sm font-medium text-emerald-600">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 dot-pulse"></span>
                  Live
                </span>
              )}
            </div>
            <div className="h-32 sm:h-40 overflow-y-auto space-y-2">
              {logs.length === 0 && !isScanning ? (
                <p className="text-sm text-slate-400 italic">Waiting for scan…</p>
              ) : (
                logs.map((log, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <ChevronRight size={13} className="mt-0.5 shrink-0 text-slate-300" />
                    <span className="text-xs sm:text-sm text-slate-600 font-mono leading-relaxed break-all">{log}</span>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Lead Feed — 1/3 on large, full width on mobile */}
        <div className="flex flex-col gap-4 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm sm:text-base font-semibold text-slate-800">Live Lead Feed</h3>
            {leads.length > 0 && (
              <span className="ml-auto text-xs font-semibold text-blue-600 bg-blue-50 px-2.5 py-1 rounded-full">
                {leads.length}
              </span>
            )}
          </div>

          {/* On large screens scroll within column; on mobile just flows */}
          <div className="space-y-4 lg:overflow-y-auto lg:max-h-[600px]">
            {leads.length === 0 ? (
              <div className="rounded-xl p-8 sm:p-10 text-center w-full" style={{ border: '2px dashed #e2e8f0' }}>
                <Search size={28} className="text-slate-300 mx-auto mb-3" />
                <p className="text-sm sm:text-base font-medium text-slate-400">No leads yet</p>
                <p className="text-xs sm:text-sm text-slate-300 mt-1">Run a scan to find buyers</p>
              </div>
            ) : (
              leads.map(lead => <LeadFeedCard key={lead.id} lead={lead} />)
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
