import React, { useEffect, useState } from 'react';
import { Database, Code2, Layers, CheckCircle2, ChevronRight, FileText } from 'lucide-react';
import axios from 'axios';

export default function DatabaseSelector({ selectedDb, setSelectedDb, includeSamples, setIncludeSamples, enableConsensus, setEnableConsensus }) {
  const [databases, setDatabases] = useState([]);
  const [schemaDdl, setSchemaDdl] = useState('');
  const [showSchemaModal, setShowSchemaModal] = useState(false);
  const [loadingSchema, setLoadingSchema] = useState(false);

  useEffect(() => {
    const fetchDbs = async () => {
      try {
        const res = await axios.get('/v1/databases');
        if (res.data && res.data.databases) {
          setDatabases(res.data.databases);
          if (res.data.databases.length > 0 && !selectedDb) {
            setSelectedDb(res.data.databases[0].db_id);
          }
        }
      } catch {
        // Fallback default databases
        setDatabases([
          { db_id: 'concert_singer', table_count: 4, tables: ['stadium', 'singer', 'concert', 'singer_in_concert'] },
          { db_id: 'student_assessment', table_count: 3, tables: ['courses', 'students', 'student_course_registrations'] },
          { db_id: 'pets_1', table_count: 3, tables: ['student', 'has_pet', 'pets'] }
        ]);
      }
    };
    fetchDbs();
  }, []);

  const handleFetchSchema = async (dbId) => {
    setLoadingSchema(true);
    setShowSchemaModal(true);
    try {
      const res = await axios.get(`/v1/databases/${dbId}/schema?include_samples=${includeSamples}`);
      setSchemaDdl(res.data.schema_ddl || 'No schema DDL returned.');
    } catch (err) {
      setSchemaDdl(`Error loading schema DDL: ${err.message}`);
    } finally {
      setLoadingSchema(false);
    }
  };

  return (
    <div className="glass-card rounded-2xl p-5 border border-slate-800/80">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <Database className="w-5 h-5 text-indigo-400" />
          <h2 className="text-base font-semibold text-slate-100">Target Database Schema</h2>
        </div>
        <button
          onClick={() => handleFetchSchema(selectedDb)}
          className="flex items-center space-x-1.5 text-xs text-indigo-400 hover:text-indigo-300 font-medium px-2.5 py-1 rounded-lg bg-indigo-500/10 border border-indigo-500/20 transition-all hover:bg-indigo-500/20"
        >
          <Code2 className="w-3.5 h-3.5" />
          <span>View Schema DDL</span>
        </button>
      </div>

      {/* Database Radio Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {databases.map((db) => {
          const isSelected = selectedDb === db.db_id;
          return (
            <button
              key={db.db_id}
              onClick={() => setSelectedDb(db.db_id)}
              className={`relative text-left p-3.5 rounded-xl border transition-all ${
                isSelected
                  ? 'bg-indigo-600/15 border-indigo-500/60 text-white glow-indigo'
                  : 'bg-slate-900/50 border-slate-800/80 text-slate-300 hover:border-slate-700 hover:bg-slate-900/80'
              }`}
            >
              <div className="flex items-start justify-between">
                <div>
                  <span className="text-xs font-mono font-semibold text-indigo-300 block mb-1">
                    {db.db_id}
                  </span>
                  <p className="text-[11px] text-slate-400 flex items-center gap-1">
                    <Layers className="w-3 h-3 text-slate-500" /> {db.table_count || db.tables?.length || 0} Tables
                  </p>
                </div>
                {isSelected && <CheckCircle2 className="w-4 h-4 text-indigo-400" />}
              </div>
            </button>
          );
        })}
      </div>

      {/* Options */}
      <div className="mt-4 pt-3 border-t border-slate-800/60 flex flex-wrap items-center justify-between gap-3 text-xs text-slate-400">
        <label className="flex items-center space-x-2 cursor-pointer select-none">
          <input
            type="checkbox"
            checked={includeSamples}
            onChange={(e) => setIncludeSamples(e.target.checked)}
            className="rounded border-slate-700 text-indigo-600 focus:ring-indigo-500 bg-slate-900"
          />
          <span>Append sample rows in prompt DDL</span>
        </label>

        <label className="flex items-center space-x-2 cursor-pointer select-none text-emerald-400 font-medium">
          <input
            type="checkbox"
            checked={enableConsensus}
            onChange={(e) => setEnableConsensus(e.target.checked)}
            className="rounded border-slate-700 text-emerald-600 focus:ring-emerald-500 bg-slate-900"
          />
          <span>🏆 Majority Voting & Self-Correction (N=5 Candidates)</span>
        </label>

        <span className="text-[11px] text-slate-500 font-mono">SQLite Read-Only Sandbox</span>
      </div>

      {/* Schema DDL Modal */}
      {showSchemaModal && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="glass-panel max-w-2xl w-full rounded-2xl border border-slate-700/80 shadow-2xl p-6 overflow-hidden flex flex-col max-h-[80vh]">
            <div className="flex items-center justify-between pb-4 border-b border-slate-800">
              <div className="flex items-center space-x-2">
                <FileText className="w-5 h-5 text-indigo-400" />
                <h3 className="text-lg font-bold text-white">Schema DDL: <span className="font-mono text-indigo-300">{selectedDb}</span></h3>
              </div>
              <button
                onClick={() => setShowSchemaModal(false)}
                className="text-slate-400 hover:text-white px-3 py-1 rounded-lg bg-slate-800 text-xs font-semibold"
              >
                Close ✕
              </button>
            </div>

            <div className="flex-1 overflow-y-auto my-4 font-mono text-xs text-emerald-400 bg-slate-950/80 p-4 rounded-xl border border-slate-800/80 leading-relaxed">
              {loadingSchema ? (
                <div className="text-slate-400 text-center py-8">Extracting table DDL schema...</div>
              ) : (
                <pre>{schemaDdl}</pre>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
