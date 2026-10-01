import React, { useState } from 'react';
import { ShieldAlert, Zap, Lock, Bug, CheckCircle2, XCircle } from 'lucide-react';
import axios from 'axios';

const ATTACK_VECTORS = [
  {
    id: 'DDL_ATTACK',
    name: 'DROP TABLE Destruction',
    category: 'Write & DDL',
    sql: 'DROP TABLE singer;',
    icon: Bug,
  },
  {
    id: 'EXFILTRATION',
    name: 'Password Column Exfiltration',
    category: 'Data Exfiltration',
    sql: 'SELECT name, password FROM users;',
    icon: Lock,
  },
  {
    id: 'MULTI_STMT',
    name: 'Multi-Statement Injection',
    category: 'Statement Chaining',
    sql: 'SELECT 1; DELETE FROM courses;',
    icon: Zap,
  },
  {
    id: 'COMMENT_SMUGGLE',
    name: 'Comment Smuggling Payload',
    category: 'Comment Injection',
    sql: 'SELECT * FROM students -- drop table songs',
    icon: ShieldAlert,
  },
  {
    id: 'SYSTEM_EXFIL',
    name: 'sqlite_master System Table Query',
    category: 'System Exfiltration',
    sql: 'SELECT * FROM sqlite_master;',
    icon: Lock,
  },
  {
    id: 'SAFE_CONTROL',
    name: 'Legitimate Control Query',
    category: 'Safe Control Query',
    sql: 'SELECT name, age FROM singer WHERE age > 30 ORDER BY age DESC;',
    icon: CheckCircle2,
  },
];

export default function RedTeamLab() {
  const [activeAttack, setActiveAttack] = useState(null);
  const [validationResult, setValidationResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleTestAttack = async (vector) => {
    setActiveAttack(vector);
    setLoading(true);
    setValidationResult(null);

    try {
      const res = await axios.post('/v1/sql/validate', { sql: vector.sql });
      setValidationResult(res.data);
    } catch (err) {
      setValidationResult({
        allowed: false,
        reasons: [`Connection error: ${err.message}`],
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="glass-card rounded-2xl p-6 border border-slate-800/80">
        <div className="flex items-center space-x-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-rose-500/20 text-rose-400 flex items-center justify-center border border-rose-500/30">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <div>
            <h2 className="text-lg font-bold text-white">⚔️ Red-Team Security Testing Lab</h2>
            <p className="text-xs text-slate-400">
              Test adversarial SQL attack vectors against the AST Validator and Connection Authorizer in real-time.
            </p>
          </div>
        </div>

        {/* Attack Buttons Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mt-5">
          {ATTACK_VECTORS.map((vec) => {
            const Icon = vec.icon;
            const isSelected = activeAttack?.id === vec.id;
            return (
              <button
                key={vec.id}
                onClick={() => handleTestAttack(vec)}
                className={`text-left p-4 rounded-xl border transition-all flex flex-col justify-between ${
                  isSelected
                    ? 'bg-rose-950/40 border-rose-500/60 text-white glow-rose'
                    : 'bg-slate-900/60 border-slate-800 text-slate-300 hover:border-slate-700 hover:bg-slate-900'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-semibold text-rose-400 font-mono">{vec.category}</span>
                    <Icon className="w-4 h-4 text-slate-400" />
                  </div>
                  <h3 className="text-sm font-bold text-slate-100">{vec.name}</h3>
                </div>
                <code className="text-[11px] font-mono text-slate-400 bg-slate-950/80 px-2 py-1 rounded mt-3 truncate block">
                  {vec.sql}
                </code>
              </button>
            );
          })}
        </div>
      </div>

      {/* Validation Outcome Panel */}
      {activeAttack && (
        <div className="glass-panel rounded-2xl p-6 border border-slate-800 shadow-xl">
          <h3 className="text-sm font-semibold text-slate-300 mb-3 flex items-center gap-2">
            Result for: <span className="font-mono text-rose-400">{activeAttack.name}</span>
          </h3>

          {loading ? (
            <div className="text-slate-400 text-center py-6 text-xs">Simulating AST Guardrail Check...</div>
          ) : validationResult ? (
            <div
              className={`p-4 rounded-xl border font-mono text-xs ${
                validationResult.allowed
                  ? 'bg-emerald-950/40 border-emerald-500/40 text-emerald-300'
                  : 'bg-rose-950/40 border-rose-500/40 text-rose-300'
              }`}
            >
              <div className="flex items-center space-x-2 text-sm font-bold mb-2">
                {validationResult.allowed ? (
                  <>
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                    <span>ALLOWED (Clean Read-Only Query)</span>
                  </>
                ) : (
                  <>
                    <XCircle className="w-5 h-5 text-rose-400" />
                    <span>BLOCKED (Intercepted by AST Validator)</span>
                  </>
                )}
              </div>

              {!validationResult.allowed && validationResult.reasons && (
                <div className="mt-2 pt-2 border-t border-rose-800/40 space-y-1">
                  <span className="font-semibold text-rose-400 font-sans">Interception Reasons:</span>
                  {validationResult.reasons.map((r, i) => (
                    <div key={i} className="text-rose-200">
                      • {r}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
