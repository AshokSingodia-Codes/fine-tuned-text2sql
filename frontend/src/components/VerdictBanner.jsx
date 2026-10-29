import React from 'react';
import { ShieldCheck, ShieldAlert, Clock, Code, AlertTriangle, RefreshCw, Copy } from 'lucide-react';

export default function VerdictBanner({ result }) {
  if (!result) return null;
  const { allowed, reasons, sql, timings_ms, retried } = result;

  const copySQL = () => sql && navigator.clipboard.writeText(sql);

  return (
    <div className="space-y-4 fade-in">
      {/* ── Verdict Header ─────────────────────────── */}
      <div className={`rounded-2xl p-5 ${allowed ? 'verdict-allowed' : 'verdict-blocked'}`}>
        <div className="flex items-start gap-3">
          <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${
            allowed ? 'bg-emerald-100' : 'bg-rose-100'
          }`}>
            {allowed
              ? <ShieldCheck className="w-5 h-5 text-emerald-600" />
              : <ShieldAlert className="w-5 h-5 text-rose-600" />}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h3 className={`font-bold text-sm ${allowed ? 'text-emerald-800' : 'text-rose-800'}`}>
                {allowed ? '✓ Query Allowed' : '✗ Blocked by Guardrail'}
              </h3>
              {result.consensus_score && (
                <span className="pill pill-emerald">🏆 Consensus: {result.consensus_score} agreed</span>
              )}
              {retried && (
                <span className="pill pill-amber">
                  <RefreshCw className="w-3 h-3" /> Self-Corrected
                </span>
              )}
            </div>
            <p className={`text-xs mt-1 ${allowed ? 'text-emerald-700' : 'text-rose-700'}`}>
              {allowed
                ? 'Passed AST validation, table/column allowlist, and read-only connection authorizer.'
                : 'Safety layer intercepted query before execution.'}
            </p>
          </div>
        </div>

        {/* Block reasons */}
        {!allowed && reasons?.length > 0 && (
          <div className="mt-4 pt-3 border-t border-rose-200">
            <p className="text-xs font-semibold text-rose-700 flex items-center gap-1 mb-2">
              <AlertTriangle className="w-3.5 h-3.5" /> Interception Reasons:
            </p>
            <ul className="space-y-1.5">
              {reasons.map((r, i) => (
                <li key={i} className="text-xs font-mono text-rose-700 bg-rose-100 border border-rose-200 rounded-lg px-3 py-1.5">
                  • {r}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* ── Generated SQL ─────────────────────────── */}
      <div className="card p-5">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Code className="w-4 h-4 text-indigo-500" />
            <span className="text-sm font-semibold text-slate-700">Generated SQL</span>
          </div>
          <div className="flex items-center gap-3">
            {timings_ms && (
              <div className="flex items-center gap-2 text-xs text-slate-400 font-mono">
                <Clock className="w-3.5 h-3.5 text-indigo-400" />
                <span>Total: {timings_ms.total_ms || 0}ms</span>
                <span className="text-slate-300">|</span>
                <span>Inf: {timings_ms.inference_ms || 0}ms</span>
                <span className="text-slate-300">|</span>
                <span>Exec: {timings_ms.execution_ms || 0}ms</span>
              </div>
            )}
            {sql && (
              <button
                onClick={copySQL}
                className="btn-secondary flex items-center gap-1.5 !py-1 !px-2.5 !text-xs"
              >
                <Copy className="w-3 h-3" /> Copy
              </button>
            )}
          </div>
        </div>
        <div className="code-block">
          <code>{sql || '-- No SQL generated'}</code>
        </div>

        {/* Attempt list */}
        {result.attempts?.length > 0 && (
          <div className="mt-4 pt-3 border-t border-slate-100">
            <p className="text-xs font-semibold text-slate-500 mb-2">
              Generation Attempts ({result.attempts.length}):
            </p>
            <div className="space-y-1.5">
              {result.attempts.map((att, idx) => (
                <div key={idx} className="flex items-center justify-between bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 text-xs font-mono">
                  <span className="text-slate-500">#{att.attempt_index ?? idx + 1}</span>
                  <code className="text-slate-700 truncate max-w-xs mx-2">{att.sql}</code>
                  <span className={`pill ${att.status === 'ok' ? 'pill-emerald' : 'pill-rose'}`}>
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
