import React, { useEffect, useState } from 'react';
import { ShieldCheck, Cpu, GitFork, Activity, Circle, Wifi, WifiOff } from 'lucide-react';
import axios from 'axios';

/* global __API_BASE__ */
const API_BASE = typeof __API_BASE__ !== 'undefined' ? __API_BASE__ : '';

export default function Header() {
  const [status, setStatus] = useState({ health: 'checking', ready: 'checking' });

  useEffect(() => {
    const check = async () => {
      try {
        const [h, r] = await Promise.all([
          axios.get(`${API_BASE}/health`).catch(() => ({ status: 0 })),
          axios.get(`${API_BASE}/ready`).catch(() => ({ status: 0 })),
        ]);
        setStatus({
          health: h.status === 200 ? 'online' : 'offline',
          ready: r.status === 200 ? 'ready' : 'warming',
        });
      } catch {
        setStatus({ health: 'offline', ready: 'offline' });
      }
    };
    check();
    const t = setInterval(check, 20000);
    return () => clearInterval(t);
  }, []);

  const isOnline = status.health === 'online';
  const isWarming = status.ready === 'warming';

  return (
    <header className="sticky top-0 z-50 bg-white border-b border-slate-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex items-center justify-between gap-4">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 flex items-center justify-center shadow-md shadow-indigo-200">
            <ShieldCheck className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-lg font-bold text-slate-900 tracking-tight">
                Text-to-SQL Assistant
              </h1>
              <span className="pill pill-indigo">v1.0 QLoRA</span>
            </div>
            <p className="text-[11px] text-slate-500 flex items-center gap-1 mt-0.5">
              <Cpu className="w-3 h-3" />
              Qwen2.5-Coder-3B · AST Guardrails · SQLite Sandbox
            </p>
          </div>
        </div>

        {/* Status + GitHub */}
        <div className="flex items-center gap-3">
          {/* API status */}
          <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-slate-50 rounded-lg border border-slate-200 text-xs">
            {isOnline ? (
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
              </span>
            ) : (
              <span className="h-2 w-2 rounded-full bg-rose-400" />
            )}
            <span className="text-slate-500">API:</span>
            <span className={`font-semibold ${isOnline ? 'text-emerald-600' : 'text-rose-500'}`}>
              {isOnline ? 'Online' : 'Offline'}
            </span>
            <span className="text-slate-300">|</span>
            <Activity className="w-3 h-3 text-indigo-400" />
            <span className="text-slate-500">Engine:</span>
            <span className="font-semibold text-indigo-600">GGUF Q4_K_M</span>
          </div>

          <a
            href="https://github.com/AshokSingodia-Codes/fine-tuned-text2sql"
            target="_blank"
            rel="noopener noreferrer"
            className="btn-secondary flex items-center gap-1.5 !py-1.5 !px-3 !text-xs"
          >
            <GitFork className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">GitHub</span>
          </a>
        </div>
      </div>

      {/* Warming banner */}
      {isWarming && (
        <div className="bg-amber-50 border-t border-amber-200 px-4 py-2 text-xs text-amber-700 flex items-center gap-2">
          <span className="animate-pulse w-2 h-2 rounded-full bg-amber-400 inline-block" />
          Model is warming up (cold start ~30s). Queries will be available shortly.
        </div>
      )}
    </header>
  );
}
