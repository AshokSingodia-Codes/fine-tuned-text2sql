import React, { useEffect, useState } from 'react';
import { BarChart3, HardDrive, Cpu, ShieldCheck, Zap, Layers } from 'lucide-react';
import axios from 'axios';

export default function MetricsDashboard() {
  const [modelInfo, setModelInfo] = useState(null);

  useEffect(() => {
    const fetchInfo = async () => {
      try {
        const res = await axios.get('/v1/model/info');
        setModelInfo(res.data);
      } catch {
        setModelInfo({
          model_name: 'Qwen2.5-Coder-3B-Instruct',
          version: '1.0-QLoRA',
          quantization: 'GGUF Q4_K_M',
        });
      }
    };
    fetchInfo();
  }, []);

  return (
    <div className="space-y-6">
      {/* Metric Cards Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="glass-card rounded-2xl p-5 border border-slate-800/80 flex items-center space-x-4">
          <div className="w-12 h-12 rounded-xl bg-indigo-500/20 text-indigo-400 flex items-center justify-center border border-indigo-500/30">
            <BarChart3 className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs text-slate-400 font-medium block">Dev Exec Accuracy</span>
            <span className="text-2xl font-bold text-white font-mono">1.1%</span>
            <span className="text-[11px] text-indigo-400 block mt-0.5">Spider Benchmark</span>
          </div>
        </div>

        <div className="glass-card rounded-2xl p-5 border border-slate-800/80 flex items-center space-x-4">
          <div className="w-12 h-12 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center border border-emerald-500/30">
            <Zap className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs text-slate-400 font-medium block">Valid SQL Rate</span>
            <span className="text-2xl font-bold text-white font-mono">100.0%</span>
            <span className="text-[11px] text-emerald-400 block mt-0.5">Format Compliant</span>
          </div>
        </div>

        <div className="glass-card rounded-2xl p-5 border border-slate-800/80 flex items-center space-x-4">
          <div className="w-12 h-12 rounded-xl bg-amber-500/20 text-amber-400 flex items-center justify-center border border-amber-500/30">
            <HardDrive className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs text-slate-400 font-medium block">GGUF Quantized Size</span>
            <span className="text-2xl font-bold text-white font-mono">1.9 GB</span>
            <span className="text-[11px] text-amber-400 block mt-0.5">Q4_K_M (69% Saving)</span>
          </div>
        </div>

        <div className="glass-card rounded-2xl p-5 border border-slate-800/80 flex items-center space-x-4">
          <div className="w-12 h-12 rounded-xl bg-rose-500/20 text-rose-400 flex items-center justify-center border border-rose-500/30">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <span className="text-xs text-slate-400 font-medium block">Red-Team Block Rate</span>
            <span className="text-2xl font-bold text-white font-mono">100.0%</span>
            <span className="text-[11px] text-rose-400 block mt-0.5">60 / 60 Intercepted</span>
          </div>
        </div>
      </div>

      {/* Model Spec Details */}
      <div className="glass-card rounded-2xl p-6 border border-slate-800/80">
        <h3 className="text-base font-bold text-slate-100 mb-4 flex items-center gap-2">
          <Cpu className="w-5 h-5 text-indigo-400" /> Architecture Details & License Specs
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs font-mono">
          <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800 space-y-2">
            <div className="flex justify-between border-b border-slate-800 pb-2">
              <span className="text-slate-400">Base Architecture:</span>
              <span className="text-indigo-300 font-semibold">{modelInfo?.model_name || 'Qwen2.5-Coder-3B-Instruct'}</span>
            </div>
            <div className="flex justify-between border-b border-slate-800 pb-2">
              <span className="text-slate-400">Fine-Tuning Method:</span>
              <span className="text-indigo-300">QLoRA (NF4 4-bit, r=16, alpha=32)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Target Projections:</span>
              <span className="text-indigo-300">All Linear (q,k,v,o,gate,up,down)</span>
            </div>
          </div>

          <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800 space-y-2">
            <div className="flex justify-between border-b border-slate-800 pb-2">
              <span className="text-slate-400">Serving Engine:</span>
              <span className="text-emerald-400 font-semibold">llama.cpp / FastAPI</span>
            </div>
            <div className="flex justify-between border-b border-slate-800 pb-2">
              <span className="text-slate-400">Database Engine:</span>
              <span className="text-emerald-400">SQLite (mode=ro, Authorizer Callback)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Dataset License:</span>
              <span className="text-emerald-400">Spider 1.0 (CC BY-SA 4.0)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
