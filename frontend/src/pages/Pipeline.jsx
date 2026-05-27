import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  Rocket, ChevronDown, ChevronUp, ExternalLink,
  Building2, UserCircle, MessageSquare, RefreshCw,
  Zap, Flame, Thermometer, CheckCircle2,
} from 'lucide-react';

const RAW_API_BASE_URL = (import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000').trim();
const API_BASE_URL = RAW_API_BASE_URL.replace(/\/+$/, '').replace(/\/api$/, '');

/* ── Helpers ─────────────────────────────────────────── */
const SIGNAL_LABELS = {
  product_request:   'Product Request',
  competitor_pain:   'Competitor Pain',
  active_evaluation: 'Active Evaluation',
  advice_seeking:    'Advice Seeking',
  urgent_need:       'Urgent Need',
  no_signal:         'No Signal',
};

const getScoreMeta = (score) => {
  if (score >= 90) return { label: 'HOT',  bg: '#fef2f2', color: '#dc2626', border: '#fecaca', dot: '#ef4444' };
  if (score >= 70) return { label: 'WARM', bg: '#fff7ed', color: '#ea580c', border: '#fed7aa', dot: '#f97316' };
  if (score >= 50) return { label: 'COLD', bg: '#eff6ff', color: '#2563eb', border: '#bfdbfe', dot: '#3b82f6' };
  return             { label: 'N/A',  bg: '#f8fafc', color: '#94a3b8', border: '#e2e8f0', dot: '#cbd5e1' };
};

const getPlatformMeta = (platform) => {
  switch (platform?.toLowerCase()) {
    case 'reddit':            return { label: 'Reddit',      bg: '#fff7ed', color: '#ea580c' };
    case 'linkedin':          return { label: 'LinkedIn',    bg: '#eff6ff', color: '#2563eb' };
    case 'x': case 'twitter': return { label: 'X / Twitter', bg: '#f8fafc', color: '#475569' };
    default:                  return { label: platform || 'Social', bg: '#f8fafc', color: '#64748b' };
  }
};

/* ── Column definitions ──────────────────────────────── */
const COLUMNS = [
  { id: 'detected',  title: 'Detected',    icon: Zap,          accent: '#6366f1', filter: () => true },
  { id: 'scored',    title: 'AI Scored',   icon: Thermometer,  accent: '#f97316', filter: l => (l.score || 0) > 0 },
  { id: 'qualified', title: 'Qualified',   icon: Flame,        accent: '#ef4444', filter: l => l.status === 'warm' || l.status === 'hot' },
  { id: 'pipeline',  title: 'In Pipeline', icon: CheckCircle2, accent: '#10b981', filter: l => l.status === 'in_pipeline' },
];

/* ── Lead Card ───────────────────────────────────────── */
function LeadCard({ lead, onPush, expandedDrafts, onToggleDraft }) {
  const score  = getScoreMeta(lead.score ?? 0);
  const plat   = getPlatformMeta(lead.platform);
  const signal = SIGNAL_LABELS[lead.signal_type] || lead.signal_type || '—';
  const isOpen = expandedDrafts[lead.id];
  const sourceUrl = lead.source_url || lead.url;
  const sourceHost = sourceUrl ? new URL(sourceUrl).hostname.replace(/^www\./, '') : null;

  return (
    <div
      id={`card-${lead.id}`}
      className="bg-white rounded-xl p-4 sm:p-5 transition-shadow hover:shadow-sm w-full"
      style={{ border: '1px solid #e2e8f0' }}
    >
      {/* Platform + Score */}
      <div className="flex items-center justify-between mb-3 gap-2">
        <span
          className="text-xs font-semibold px-2 py-1 rounded-md shrink-0"
          style={{ background: plat.bg, color: plat.color }}
        >
          {plat.label}
        </span>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          {sourceUrl && (
            <a href={sourceUrl} target="_blank" rel="noreferrer"
               className="text-slate-300 hover:text-blue-500 transition-colors">
              <ExternalLink size={14} />
            </a>
          )}
          <span
            className="inline-flex items-center gap-1.5 text-xs font-bold px-2.5 py-1 rounded-full whitespace-nowrap"
            style={{ background: score.bg, color: score.color, border: `1px solid ${score.border}` }}
          >
            <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: score.dot }}></span>
            {score.label} {lead.score > 0 ? lead.score : ''}
          </span>
        </div>
      </div>

      <p className="text-sm font-semibold text-blue-600 mb-2">{signal}</p>

      <p className="text-sm text-slate-500 line-clamp-2 leading-relaxed mb-3">
        {lead.pain_point || lead.content || '—'}
      </p>

      <div className="mb-3 rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500" style={{ border: '1px solid #e2e8f0' }}>
        <div><span className="font-semibold text-slate-700">Source:</span> {plat.label}</div>
        <div><span className="font-semibold text-slate-700">Matched From:</span> {sourceHost || `${plat.label} public post search`}</div>
      </div>

      {lead.analysis_error && (
        <p className="text-xs text-rose-500 mb-3 line-clamp-2">
          AI: {lead.analysis_error}
        </p>
      )}

      {(lead.company_hint || lead.role_hint) && (
        <div className="flex flex-wrap gap-2 mb-3">
          {lead.company_hint && (
            <span className="flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-md bg-slate-50 text-slate-500 border border-slate-100">
              <Building2 size={11} /> {lead.company_hint}
            </span>
          )}
          {lead.role_hint && (
            <span className="flex items-center gap-1 text-xs font-medium px-2 py-1 rounded-md bg-slate-50 text-slate-500 border border-slate-100">
              <UserCircle size={11} /> {lead.role_hint}
            </span>
          )}
        </div>
      )}

      <div className="space-y-2">
        {lead.status !== 'in_pipeline' ? (
          <div className="flex gap-2">
            <button
              id={`push-${lead.id}`}
              onClick={() => onPush(lead.id)}
              className="w-full py-2.5 rounded-lg text-sm font-semibold text-white bg-blue-600 hover:bg-blue-700 flex items-center justify-center gap-2 transition-colors"
            >
              <Rocket size={13} /> Push to Pipeline
            </button>
            <button
              type="button"
              onClick={() => onPush(lead.id, { dismiss: true })}
              className="px-3 py-2.5 rounded-lg text-sm font-semibold text-slate-600 hover:bg-slate-50 transition-colors"
              style={{ border: '1px solid #e2e8f0' }}
            >
              Not a Fit
            </button>
          </div>
        ) : (
          <div className="w-full py-2.5 rounded-lg text-sm font-semibold flex items-center justify-center gap-2 text-emerald-600 bg-emerald-50 border border-emerald-100">
            <CheckCircle2 size={13} /> In Pipeline
          </div>
        )}

        {lead.outreach_draft && (
          <div style={{ borderTop: '1px solid #f1f5f9', paddingTop: '10px' }}>
            <button
              onClick={() => onToggleDraft(lead.id)}
              className="w-full flex items-center justify-between text-sm font-medium text-slate-400 hover:text-slate-600 transition-colors"
            >
              <span className="flex items-center gap-1.5 min-w-0">
                <MessageSquare size={13} className="shrink-0" /> Outreach Draft
              </span>
              {isOpen ? <ChevronUp size={13} className="shrink-0" /> : <ChevronDown size={13} className="shrink-0" />}
            </button>
            {isOpen && (
              <div
                className="mt-3 p-3 rounded-lg text-sm text-slate-600 italic leading-relaxed"
                style={{ background: '#f8fafc', borderLeft: '3px solid #bfdbfe' }}
              >
                "{lead.outreach_draft}"
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Pipeline Page ───────────────────────────────────── */
const Pipeline = () => {
  const [leads, setLeads]                   = useState([]);
  const [isLoading, setIsLoading]           = useState(true);
  const [expandedDrafts, setExpandedDrafts] = useState({});

  const fetchLeads = useCallback(async (showLoading = false) => {
    if (showLoading) setIsLoading(true);
    try {
      const r = await axios.get(`${API_BASE_URL}/api/leads`);
      setLeads(r.data);
    } catch (e) { console.error(e); }
    finally { if (showLoading) setIsLoading(false); }
  }, []);

  useEffect(() => {
    fetchLeads(true);
    const t = setInterval(() => fetchLeads(), 15000);
    return () => clearInterval(t);
  }, [fetchLeads]);

  const toggleDraft    = (id) => setExpandedDrafts(p => ({ ...p, [id]: !p[id] }));
  const pushToPipeline = async (leadId, opts = {}) => {
    try {
      if (opts.dismiss) {
        await axios.delete(`${API_BASE_URL}/api/leads/${leadId}`);
      } else {
        await axios.post(`${API_BASE_URL}/api/leads/${leadId}/push`);
      }
      fetchLeads();
    } catch (e) { console.error(e); alert('Failed to update lead.'); }
  };

  return (
    <div className="p-4 sm:p-6 lg:p-8 flex flex-col w-full" style={{ background: '#f8fafc', minHeight: '100%' }}>

      {/* Header */}
      <div className="flex flex-wrap items-start sm:items-center justify-between gap-3 mb-6 shrink-0">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900">Sales Pipeline</h1>
          <p className="text-sm sm:text-base text-slate-500 mt-0.5">Review, qualify, and push leads to your CRM.</p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-3 text-xs sm:text-sm font-medium text-slate-400 shrink-0">
          <div className="flex items-center gap-2">
            <RefreshCw size={13} className={`text-blue-500 ${isLoading ? 'spin' : ''}`} />
            Auto-refreshing every 15s
          </div>
          <span className="text-slate-500">
            Source: <span className="font-semibold text-slate-700">Reddit only</span>
          </span>
        </div>
      </div>

      {/* Kanban — horizontal scroll, each column fills proportionally */}
      <div className="flex gap-4 overflow-x-auto pb-4 w-full" style={{ flex: '1 1 auto' }}>
        {COLUMNS.map(col => {
          const colLeads = leads.filter(col.filter);
          const ColIcon  = col.icon;
          return (
            <div
              key={col.id}
              className="flex flex-col shrink-0"
              style={{ width: 'min(280px, calc(90vw))', flex: '1 1 250px', minWidth: '220px', maxWidth: '340px' }}
            >
              {/* Column header */}
              <div
                className="flex items-center justify-between px-4 py-3 rounded-t-xl bg-white shrink-0"
                style={{
                  borderTop: `3px solid ${col.accent}`,
                  border: `1px solid #e2e8f0`,
                  borderTopColor: col.accent,
                }}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <ColIcon size={15} style={{ color: col.accent }} className="shrink-0" />
                  <span className="text-sm font-semibold text-slate-700 truncate">{col.title}</span>
                </div>
                <span
                  className="text-xs font-bold px-2 py-0.5 rounded-full shrink-0 ml-2"
                  style={{ background: `${col.accent}18`, color: col.accent }}
                >
                  {colLeads.length}
                </span>
              </div>

              {/* Column body */}
              <div
                className="flex-1 overflow-y-auto p-3 space-y-3 rounded-b-xl"
                style={{
                  background: '#f1f5f9',
                  border: '1px solid #e2e8f0',
                  borderTop: 'none',
                  maxHeight: 'calc(100vh - 220px)',
                  minHeight: '120px',
                }}
              >
                {colLeads.length === 0 ? (
                  <div
                    className="h-20 rounded-xl flex items-center justify-center"
                    style={{ border: '2px dashed #e2e8f0' }}
                  >
                    <p className="text-sm text-slate-300 font-medium">No leads</p>
                  </div>
                ) : (
                  colLeads.map(lead => (
                    <LeadCard
                      key={lead.id}
                      lead={lead}
                      onPush={pushToPipeline}
                      expandedDrafts={expandedDrafts}
                      onToggleDraft={toggleDraft}
                    />
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default Pipeline;
