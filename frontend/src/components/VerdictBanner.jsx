import React from 'react';
import { ShieldCheck, ShieldAlert, Clock, Code, AlertTriangle, RefreshCw } from 'lucide-react';

export default function VerdictBanner({ result }) {
  if (!result) return null;

  const { allowed, reasons, sql, timings_ms, retried, row_count, truncated } = result;

  return (
    <div className="space-y-4">
      {/* Verdict Alert Header */}
      <div
        className={`rounded-2xl p-5 border transition-all ${
          allowed
            ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-100 glow-emerald'
            : 'bg-rose-950/40 border-rose-500/40 text-rose-100 glow-rose'
        }`}
      >
        <div className="flex items-start justify-between">
          <div className="flex items-center space-x-3">
            <div
              className={`w-10 h-10 rounded-xl flex items-center justify-center ${
                allowed ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
              }`}
            >
              {allowed ? <ShieldCheck className="w-6 h-6" /> : <ShieldAlert className="w-6 h-6" />}
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h3 className="text-base font-bold">
                  {allowed ? 'VERDICT: ALLOWED' : 'VERDICT: BLOCKED BY GUARDRAIL'}
                </h3>
                {result.consensus_score && (
                  <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 flex items-center gap-1 font-mono font-semibold">
                    🏆 Consensus Vote: {result.consensus_score} Agreed
                  </span>
                )}
                {retried && (
                  <span className="text-[11px] px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 flex items-center gap-1 font-mono">
                    <RefreshCw className="w-3 h-3 animate-spin" /> Retried on SQL Error
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-300 mt-0.5">
                {allowed
                  ? 'Query passed all AST AST structure checks, table/column denylists, and connection authorizers.'
                  : 'Safety layer intercepted query before execution.'}
              </p>
            </div>
          </div>
        </div>

        {/* Block Reasons if Blocked */}
        {!allowed && reasons && reasons.length > 0 && (
          <div className="mt-4 pt-3 border-t border-rose-500/20">
            <span className="text-xs font-semibold text-rose-300 flex items-center gap-1 mb-2">
              <AlertTriangle className="w-3.5 h-3.5" /> Interception Reasons:
            </span>
            <ul className="space-y-1">
              {reasons.map((r, i) => (
                <li key={i} className="text-xs text-rose-200/90 font-mono bg-rose-900/30 px-3 py-1.5 rounded-lg border border-rose-800/40">
                  • {r}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Generated SQL Code Block */}
      <div className="glass-card rounded-2xl p-5 border border-slate-800/80">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center space-x-2 text-xs font-semibold text-slate-300">
            <Code className="w-4 h-4 text-indigo-400" />
            <span>Generated SQLite Query</span>
          </div>
          <div className="flex items-center space-x-3">
            {sql && (
              <button
                type="button"
                onClick={() => navigator.clipboard.writeText(sql)}
                className="text-xs px-2.5 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 transition-colors"
              >
                Copy SQL
              </button>
            )}
            {timings_ms && (
              <div className="flex items-center space-x-3 text-xs text-slate-400 font-mono">
                <span className="flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5 text-indigo-400" /> Total: {timings_ms.total_ms || 0}ms
                </span>
                <span>(Inf: {timings_ms.inference_ms || 0}ms | Val: {timings_ms.validation_ms || 0}ms | Exec: {timings_ms.execution_ms || 0}ms)</span>
              </div>
            )}
          </div>
        </div>

        <div className="bg-slate-950 p-4 rounded-xl border border-slate-800/80 font-mono text-sm text-emerald-400 overflow-x-auto">
          <code>{sql || '-- No SQL generated'}</code>
        </div>

        {/* Sanitized Attempts Transparency List */}
        {result.attempts && result.attempts.length > 0 && (
          <div className="mt-4 pt-3 border-t border-slate-800/60">
            <span className="text-xs font-semibold text-slate-400 block mb-2 font-mono">
              Generation Attempts ({result.attempts.length}):
            </span>
            <div className="space-y-1.5">
              {result.attempts.map((att, idx) => (
                <div key={idx} className="flex items-center justify-between bg-slate-900/60 px-3 py-1.5 rounded-lg border border-slate-800/70 text-xs font-mono">
                  <span className="text-slate-400">Attempt #{att.attempt_index !== undefined ? att.attempt_index : idx + 1}:</span>
                  <code className="text-slate-300 truncate max-w-md mx-2">{att.sql}</code>
                  <span className={`px-2 py-0.5 rounded text-[10px] font-semibold ${att.status === 'ok' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-rose-500/20 text-rose-300'}`}>
                    {att.status}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

