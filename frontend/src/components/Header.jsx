import React, { useEffect, useState } from 'react';
import { Database, ShieldCheck, Cpu, GitFork, Activity } from 'lucide-react';
import axios from 'axios';

export default function Header() {
  const [status, setStatus] = useState({ health: 'checking', ready: 'checking' });

  useEffect(() => {
    const checkStatus = async () => {
      try {
        const [resH, resR] = await Promise.all([
          axios.get('/health').catch(() => ({ status: 500 })),
          axios.get('/ready').catch(() => ({ status: 500 }))
        ]);
        setStatus({
          health: resH.status === 200 ? 'online' : 'offline',
          ready: resR.status === 200 ? 'ready' : 'warming'
        });
      } catch {
        setStatus({ health: 'offline', ready: 'offline' });
      }
    };
    checkStatus();
    const interval = setInterval(checkStatus, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="sticky top-0 z-50 glass-panel border-b border-slate-800/80 px-6 py-4">
      <div className="max-w-7xl mx-auto flex items-center justify-between">
        {/* Brand */}
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-600 to-violet-500 flex items-center justify-center shadow-lg shadow-indigo-500/30">
            <ShieldCheck className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-bold bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
                Guarded Text-to-SQL
              </h1>
              <span className="text-xs px-2 py-0.5 rounded-full bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 font-medium">
                v1.0 QLoRA
              </span>
            </div>
            <p className="text-xs text-slate-400 flex items-center gap-1.5 mt-0.5">
              <Cpu className="w-3 h-3 text-indigo-400" /> Qwen2.5-Coder-3B Served Behind Real-Time AST Guardrails
            </p>
          </div>
        </div>

        {/* Status Indicators & Actions */}
        <div className="flex items-center space-x-4">
          <div className="hidden md:flex items-center space-x-3 px-3 py-1.5 rounded-lg bg-slate-900/60 border border-slate-800 text-xs">
            <div className="flex items-center space-x-1.5">
              <span className={`w-2 h-2 rounded-full ${status.health === 'online' ? 'bg-emerald-400 animate-pulse' : 'bg-rose-500'}`} />
              <span className="text-slate-300">API Status:</span>
              <span className={status.health === 'online' ? 'text-emerald-400 font-semibold' : 'text-rose-400 font-semibold'}>
                {status.health.toUpperCase()}
              </span>
            </div>
            <span className="text-slate-700">|</span>
            <div className="flex items-center space-x-1.5">
              <Activity className="w-3.5 h-3.5 text-indigo-400" />
              <span className="text-slate-300">Model Engine:</span>
              <span className="text-indigo-400 font-semibold">GGUF Q4_K_M</span>
            </div>
          </div>

          <a
            href="https://github.com/AshokSingodia-Codes/fine-tuned-text2sql"
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-center space-x-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition-colors border border-slate-700/60"
          >
            <GitFork className="w-4 h-4" />
            <span className="hidden sm:inline">GitHub Repo</span>
          </a>
        </div>
      </div>

      {/* Model Warming Alert Banner */}
      {status.ready === 'warming' && (
        <div className="mt-3 py-2 px-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-300 text-xs flex items-center justify-between">
          <span className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
            Model is initializing / waking up from sleep (~1.9 GB download on first cold start). Query processing will be available in a few moments.
          </span>
        </div>
      )}

      {/* Demo Schema Disclaimers Banner */}
      <div className="mt-2 py-1.5 px-4 rounded-lg bg-indigo-950/40 border border-indigo-800/40 text-indigo-300/80 text-[11px] flex items-center justify-between font-mono">
        <span>
          ℹ️ DEMO NOTICE: Demo queries execute on the read-only Chinook SQLite demo database. Chinook is NOT part of the Spider training/dev benchmark and accuracy is not measured on it.
        </span>
      </div>
    </header>
  );
}

