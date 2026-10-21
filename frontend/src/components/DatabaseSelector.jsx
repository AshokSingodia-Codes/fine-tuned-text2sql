import React, { useEffect, useRef, useState } from 'react';
import {
  Database, Code2, Layers, CheckCircle2, Upload, FileText,
  X, AlertCircle, Search, Trash2, HardDrive, Tag,
} from 'lucide-react';
import axios from 'axios';

/* global __API_BASE__ */
const API_BASE = typeof __API_BASE__ !== 'undefined' ? __API_BASE__ : '';

export default function DatabaseSelector({
  selectedDb, setSelectedDb,
  includeSamples, setIncludeSamples,
  enableConsensus, setEnableConsensus,
}) {
  const [databases, setDatabases]         = useState([]);
  const [schemaDdl, setSchemaDdl]         = useState('');
  const [showSchemaModal, setShowSchemaModal] = useState(false);
  const [loadingSchema, setLoadingSchema] = useState(false);
  const [uploadState, setUploadState]     = useState('idle'); // idle|uploading|success|error
  const [uploadMsg, setUploadMsg]         = useState('');
  const [dragOver, setDragOver]           = useState(false);
  const [searchTerm, setSearchTerm]       = useState('');
  const [deletingId, setDeletingId]       = useState(null);
  const fileRef = useRef(null);

  /* ── fetch DB list ──────────────────────────────────────────── */
  const fetchDbs = async () => {
    try {
      const res = await axios.get(`${API_BASE}/v1/databases`);
      if (res.data?.databases?.length > 0) {
        setDatabases(res.data.databases);
        if (!selectedDb) setSelectedDb(res.data.databases[0].db_id);
      }
    } catch {
      setDatabases([
        { db_id: 'concert_singer',    table_count: 4, source: 'builtin' },
        { db_id: 'student_assessment',table_count: 3, source: 'builtin' },
        { db_id: 'pets_1',            table_count: 3, source: 'builtin' },
      ]);
    }
  };

  useEffect(() => { fetchDbs(); }, []);

  /* ── schema DDL modal ───────────────────────────────────────── */
  const handleFetchSchema = async (dbId) => {
    setLoadingSchema(true);
    setShowSchemaModal(true);
    try {
      const res = await axios.get(`${API_BASE}/v1/databases/${dbId}/schema?include_samples=${includeSamples}`);
      setSchemaDdl(res.data.schema_ddl || 'No schema DDL returned.');
    } catch (err) {
      setSchemaDdl(`Error: ${err.message}`);
    } finally {
      setLoadingSchema(false);
    }
  };

  /* ── upload ─────────────────────────────────────────────────── */
  const handleUpload = async (file) => {
    if (!file) return;
    if (!file.name.endsWith('.sqlite') && !file.name.endsWith('.db')) {
      setUploadState('error');
      setUploadMsg('Only .sqlite or .db files are supported.');
      return;
    }
    setUploadState('uploading');
    setUploadMsg('');
    const form = new FormData();
    form.append('file', file);
    try {
      const res = await axios.post(`${API_BASE}/v1/databases/upload`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      const renamed = res.data.renamed ? ` (saved as "${res.data.db_id}")` : '';
      const sizeKB  = (res.data.size_bytes / 1024).toFixed(1);
      setUploadState('success');
      setUploadMsg(`"${res.data.db_id}" uploaded — ${res.data.table_count} tables · ${sizeKB} KB${renamed}`);
      await fetchDbs();
      setSelectedDb(res.data.db_id);
    } catch (err) {
      setUploadState('error');
      setUploadMsg(err.response?.data?.detail || err.message);
    }
  };

  /* ── delete uploaded DB ─────────────────────────────────────── */
  const handleDelete = async (dbId) => {
    if (!window.confirm(`Delete "${dbId}"? This cannot be undone.`)) return;
    setDeletingId(dbId);
    try {
      await axios.delete(`${API_BASE}/v1/databases/${dbId}`);
      if (selectedDb === dbId) setSelectedDb(null);
      await fetchDbs();
    } catch (err) {
      alert(err.response?.data?.detail || err.message);
    } finally {
      setDeletingId(null);
    }
  };

  const onDrop = (e) => {
    e.preventDefault(); setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleUpload(file);
  };

  /* ── filter ─────────────────────────────────────────────────── */
  const filtered = databases.filter((db) =>
    db.db_id.toLowerCase().includes(searchTerm.toLowerCase())
  );
  const showSearch = databases.length > 8;

  /* ── size helper ─────────────────────────────────────────────── */
  const fmtSize = (bytes) => {
    if (!bytes) return '';
    if (bytes < 1_048_576) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / 1_048_576).toFixed(1)} MB`;
  };

  return (
    <div className="card p-5 fade-in">
      {/* ── Header ──────────────────────────────────────────── */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Database className="w-4 h-4 text-indigo-500" />
          <h2 className="text-sm font-semibold text-slate-800">Target Database</h2>
          <span className="pill pill-slate">{databases.length} available</span>
        </div>
        {selectedDb && (
          <button
            onClick={() => handleFetchSchema(selectedDb)}
            className="btn-secondary flex items-center gap-1.5 !py-1 !px-2.5 !text-xs"
          >
            <Code2 className="w-3.5 h-3.5 text-indigo-500" /> View Schema DDL
          </button>
        )}
      </div>

      {/* ── Search ──────────────────────────────────────────── */}
      {showSearch && (
        <div className="relative mb-3">
          <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder={`Search ${databases.length} databases…`}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="input-field !py-1.5 !pl-8 !text-xs"
          />
          {searchTerm && (
            <button
              onClick={() => setSearchTerm('')}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      )}

      {/* ── DB Cards Grid ───────────────────────────────────── */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2 mb-4 max-h-64 overflow-y-auto pr-1">
        {filtered.length === 0 && (
          <div className="col-span-4 text-center text-xs text-slate-400 py-6">
            No databases match "{searchTerm}"
          </div>
        )}
        {filtered.map((db) => {
          const sel = selectedDb === db.db_id;
          const isUploaded = db.source === 'uploaded';
          return (
            <div
              key={db.db_id}
              className={`relative group text-left p-3 rounded-xl border transition-all cursor-pointer ${
                sel
                  ? 'bg-indigo-50 border-indigo-300 shadow-sm shadow-indigo-100'
                  : 'bg-white border-slate-200 hover:border-indigo-200 hover:bg-slate-50'
              }`}
              onClick={() => setSelectedDb(db.db_id)}
            >
              <div className="flex items-start justify-between gap-1">
                <div className="min-w-0">
                  <span className={`text-xs font-semibold font-mono block truncate ${sel ? 'text-indigo-700' : 'text-slate-700'}`}>
                    {db.db_id}
                  </span>
                  <p className="text-[11px] text-slate-400 flex items-center gap-1 mt-0.5">
                    <Layers className="w-2.5 h-2.5 shrink-0" />
                    {db.table_count} tables
                    {db.size_bytes > 0 && (
                      <span className="text-slate-300 ml-0.5">· {fmtSize(db.size_bytes)}</span>
                    )}
                  </p>
                </div>
                <div className="flex flex-col items-end gap-1 shrink-0">
                  {sel && <CheckCircle2 className="w-3.5 h-3.5 text-indigo-500" />}
                  {isUploaded && (
                    <span className="text-[9px] px-1.5 py-0.5 bg-amber-50 text-amber-600 border border-amber-200 rounded-full font-semibold">
                      uploaded
                    </span>
                  )}
                </div>
              </div>

              {/* Delete button — only for uploaded DBs */}
              {isUploaded && (
                <button
                  onClick={(e) => { e.stopPropagation(); handleDelete(db.db_id); }}
                  disabled={deletingId === db.db_id}
                  className="absolute top-1.5 right-1.5 opacity-0 group-hover:opacity-100 transition-opacity p-0.5 rounded text-rose-400 hover:text-rose-600 hover:bg-rose-50"
                  title="Delete this uploaded database"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* ── Upload Zone ─────────────────────────────────────── */}
      <div className="border-t border-slate-100 pt-4">
        <p className="text-xs font-semibold text-slate-600 mb-2 flex items-center gap-1.5">
          <Upload className="w-3.5 h-3.5 text-indigo-500" />
          Upload Your Own SQLite Database
        </p>

        <div
          className={`upload-zone flex flex-col items-center justify-center py-5 px-4 text-center ${dragOver ? 'drag-over' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
          onDragLeave={() => setDragOver(false)}
          onDrop={onDrop}
          onClick={() => fileRef.current?.click()}
        >
          {uploadState === 'uploading' ? (
            <>
              <div className="w-5 h-5 border-2 border-indigo-400 border-t-transparent rounded-full animate-spin mb-2" />
              <p className="text-sm font-medium text-indigo-600">Uploading…</p>
            </>
          ) : (
            <>
              <HardDrive className="w-6 h-6 text-indigo-400 mb-2" />
              <p className="text-sm font-medium text-slate-600">Drag & drop or click to browse</p>
              <p className="text-xs text-slate-400 mt-1">.sqlite or .db · max 50 MB · read-only sandbox</p>
            </>
          )}
          <input ref={fileRef} type="file" accept=".sqlite,.db" className="hidden"
            onChange={(e) => handleUpload(e.target.files?.[0])} />
        </div>

        {uploadState === 'success' && (
          <div className="mt-2 flex items-center gap-2 text-xs text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg px-3 py-2">
            <CheckCircle2 className="w-3.5 h-3.5 shrink-0" /> {uploadMsg}
          </div>
        )}
        {uploadState === 'error' && (
          <div className="mt-2 flex items-center gap-2 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-lg px-3 py-2">
            <AlertCircle className="w-3.5 h-3.5 shrink-0" /> {uploadMsg}
          </div>
        )}

        <p className="text-[11px] text-slate-400 mt-2 flex items-center gap-1">
          <span className="text-amber-500">⚠</span>
          All queries run in a read-only sandbox. DROP / INSERT / UPDATE are always blocked.
        </p>
      </div>

      {/* ── Options ─────────────────────────────────────────── */}
      <div className="border-t border-slate-100 pt-3 mt-3 flex flex-wrap gap-4 text-xs text-slate-600">
        <label className="flex items-center gap-2 cursor-pointer select-none">
          <input type="checkbox" checked={includeSamples}
            onChange={(e) => setIncludeSamples(e.target.checked)}
            className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-400" />
          Include sample rows in schema prompt
        </label>
        <label className="flex items-center gap-2 cursor-pointer select-none text-indigo-700 font-medium">
          <input type="checkbox" checked={enableConsensus}
            onChange={(e) => setEnableConsensus(e.target.checked)}
            className="rounded border-slate-300 text-indigo-600 focus:ring-indigo-400" />
          🏆 Majority Voting & Self-Correction (N=5)
        </label>
        <span className="ml-auto text-[11px] text-slate-400">SQLite · Read-Only Sandbox</span>
      </div>

      {/* ── Schema DDL Modal ─────────────────────────────────── */}
      {showSchemaModal && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl border border-slate-200 shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
            <div className="flex items-center justify-between p-5 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-indigo-500" />
                <h3 className="font-semibold text-slate-800">Schema DDL —
                  <span className="font-mono text-indigo-600 ml-1">{selectedDb}</span>
                </h3>
              </div>
              <button onClick={() => setShowSchemaModal(false)}
                className="btn-secondary !py-1 !px-2.5 flex items-center gap-1">
                <X className="w-3.5 h-3.5" /> Close
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-5">
              {loadingSchema
                ? <div className="text-center text-slate-400 py-8 text-sm">Loading schema…</div>
                : <pre className="code-block text-xs">{schemaDdl}</pre>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
