import React, { useState } from 'react';
import Header from './components/Header';
import DatabaseSelector from './components/DatabaseSelector';
import QueryWorkspace from './components/QueryWorkspace';
import VerdictBanner from './components/VerdictBanner';
import ResultTable from './components/ResultTable';
import RedTeamLab from './components/RedTeamLab';
import MetricsDashboard from './components/MetricsDashboard';
import { MessageSquare, ShieldAlert, BarChart3 } from 'lucide-react';
import axios from 'axios';

export default function App() {
  const [selectedDb, setSelectedDb] = useState('concert_singer');
  const [includeSamples, setIncludeSamples] = useState(false);
  const [enableConsensus, setEnableConsensus] = useState(true);
  const [activeTab, setActiveTab] = useState('workspace'); // 'workspace' | 'redteam' | 'metrics'
  
  const [loading, setLoading] = useState(false);
  const [queryResult, setQueryResult] = useState(null);

  const handleExecuteQuery = async (question) => {
    setLoading(true);
    setQueryResult(null);

    try {
      const res = await axios.post('/v1/query', {
        db_id: selectedDb,
        question: question,
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

  return (
    <div className="min-h-screen flex flex-col bg-[#0B0F17]">
      <Header />

      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Navigation Tabs */}
        <div className="flex items-center space-x-2 border-b border-slate-800 pb-3">
          <button
            onClick={() => setActiveTab('workspace')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
              activeTab === 'workspace'
                ? 'bg-indigo-600/20 text-indigo-400 border border-indigo-500/40 glow-indigo'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
            }`}
          >
            <MessageSquare className="w-4 h-4" />
            <span>Text-to-SQL Workspace</span>
          </button>

          <button
            onClick={() => setActiveTab('redteam')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
              activeTab === 'redteam'
                ? 'bg-rose-600/20 text-rose-400 border border-rose-500/40 glow-rose'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
            }`}
          >
            <ShieldAlert className="w-4 h-4" />
            <span>Red-Team Security Lab</span>
          </button>

          <button
            onClick={() => setActiveTab('metrics')}
            className={`flex items-center space-x-2 px-4 py-2 rounded-xl text-xs font-semibold transition-all ${
              activeTab === 'metrics'
                ? 'bg-emerald-600/20 text-emerald-400 border border-emerald-500/40 glow-emerald'
                : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900/60'
            }`}
          >
            <BarChart3 className="w-4 h-4" />
            <span>Model Performance Metrics</span>
          </button>
        </div>

        {/* Tab Content */}
        {activeTab === 'workspace' && (
          <div className="space-y-6">
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
              <div className="space-y-6 animate-fadeIn">
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

        {activeTab === 'redteam' && <RedTeamLab />}

        {activeTab === 'metrics' && <MetricsDashboard />}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 py-4 text-center text-xs text-slate-500 font-mono">
        Guarded Text-to-SQL Assistant • Fine-Tuned QLoRA Qwen2.5-Coder-3B • FastAPI & React
      </footer>
    </div>
  );
}
