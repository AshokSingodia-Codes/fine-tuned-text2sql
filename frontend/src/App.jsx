import React, { useState } from 'react';
import Header from './components/Header';
import DatabaseSelector from './components/DatabaseSelector';
import QueryWorkspace from './components/QueryWorkspace';
import VerdictBanner from './components/VerdictBanner';
import ResultTable from './components/ResultTable';
import RedTeamLab from './components/RedTeamLab';
import MetricsDashboard from './components/MetricsDashboard';
import { MessageSquare, ShieldAlert, BarChart3, Code } from 'lucide-react';
import axios from 'axios';

// __API_BASE__ is injected at Vite build time via vite.config.js define.
// Empty string in local dev (uses proxy). Set VITE_API_BASE_URL on Netlify.
/* global __API_BASE__ */
const API_BASE = typeof __API_BASE__ !== 'undefined' ? __API_BASE__ : '';

export default function App() {
  const [selectedDb, setSelectedDb] = useState('concert_singer');
  const [includeSamples, setIncludeSamples] = useState(false);
  const [enableConsensus, setEnableConsensus] = useState(false);
  const [activeTab, setActiveTab] = useState('workspace');
  const [loading, setLoading] = useState(false);
  const [queryResult, setQueryResult] = useState(null);

  const handleExecuteQuery = async (question) => {
    setLoading(true);
    setQueryResult(null);
    try {
      const res = await axios.post(`${API_BASE}/v1/query`, {
        db_id: selectedDb,
        question,
        include_sample_rows: includeSamples,
        enable_consensus: enableConsensus,
        n_samples: 5,
      });
      setQueryResult(res.data);
    } catch (err) {
      setQueryResult({
        allowed: false,
        reasons: [`API error: ${err.response?.data?.detail || err.message}`],
        sql: '',
        columns: [],
        rows: [],
        row_count: 0,
      });
    } finally {
      setLoading(false);
    }
  };

  const tabs = [
    { id: 'workspace', label: 'Text-to-SQL Workspace', icon: MessageSquare, theme: 'active-indigo' },
    { id: 'redteam',   label: 'Security Red-Team Lab', icon: ShieldAlert,   theme: 'active-rose' },
    { id: 'metrics',   label: 'Model Metrics',         icon: BarChart3,     theme: 'active-teal' },
  ];

  return (
    <div className="min-h-screen flex flex-col bg-slate-50">
      <Header />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 space-y-5">

        {/* ── Info banner ───────────────────────────────── */}
        <div className="bg-blue-50 border border-blue-200 rounded-xl px-4 py-3 text-xs text-blue-700 flex items-start gap-2">
          <span className="text-base mt-0.5">ℹ️</span>
          <span>
            <strong>Demo:</strong> Queries run against read-only SQLite databases.
            Upload your own <code className="bg-blue-100 px-1 rounded">.sqlite</code> file below to query your own data.
            DROP / INSERT / UPDATE are always blocked by the AST guardrail.
          </span>
        </div>

        {/* ── Nav tabs ─────────────────────────────── */}
        <div className="flex items-center gap-1.5 border-b border-slate-200 pb-3">
          {tabs.map(({ id, label, icon: Icon, theme }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`nav-tab ${activeTab === id ? theme : ''}`}
            >
              <Icon className="w-4 h-4" />
              <span className="hidden sm:inline">{label}</span>
              <span className="sm:hidden">{label.split(' ')[0]}</span>
            </button>
          ))}
        </div>

        {/* ── Tab content ─────────────────────────────── */}
        {activeTab === 'workspace' && (
          <div className="space-y-5">
            <DatabaseSelector
              selectedDb={selectedDb}
              setSelectedDb={setSelectedDb}
              includeSamples={includeSamples}
              setIncludeSamples={setIncludeSamples}
              enableConsensus={enableConsensus}
              setEnableConsensus={setEnableConsensus}
            />
            <QueryWorkspace
              selectedDb={selectedDb}
              onExecute={handleExecuteQuery}
              loading={loading}
            />
            {queryResult && (
              <div className="space-y-5">
                <VerdictBanner result={queryResult} />
                {queryResult.allowed && (
                  <ResultTable
                    columns={queryResult.columns}
                    rows={queryResult.rows}
                    rowCount={queryResult.row_count}
                    truncated={queryResult.truncated}
                  />
                )}
              </div>
            )}
          </div>
        )}

        {activeTab === 'redteam'  && <RedTeamLab />}
        {activeTab === 'metrics'  && <MetricsDashboard />}
      </main>

      {/* ── Footer ─────────────────────────────────── */}
      <footer className="bg-white border-t border-slate-200 py-4 px-6">
        <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2 text-xs text-slate-400">
          <span>
            Text-to-SQL Assistant · QLoRA fine-tuned Qwen2.5-Coder-3B ·
            <strong className="text-slate-500"> Non-commercial research demo</strong>
          </span>
          <div className="flex items-center gap-3">
            <span>Built with Qwen · FastAPI · React · sqlglot</span>
            <a
              href="https://github.com/AshokSingodia-Codes/fine-tuned-text2sql"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-indigo-600 hover:text-indigo-800 font-medium"
            >
              <Code className="w-3.5 h-3.5" /> Source Code
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
