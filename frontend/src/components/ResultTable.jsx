import React, { useState } from 'react';
import { Table as TableIcon, Download, Search, AlertCircle } from 'lucide-react';

export default function ResultTable({ columns, rows, rowCount, truncated }) {
  const [filter, setFilter] = useState('');

  if (!columns || columns.length === 0) {
    return (
      <div className="card p-10 text-center fade-in">
        <AlertCircle className="w-8 h-8 text-slate-300 mx-auto mb-2" />
        <p className="text-sm text-slate-400">Query returned no rows.</p>
      </div>
    );
  }

  const filteredRows = filter
    ? rows.filter((row) => row.some((v) => String(v).toLowerCase().includes(filter.toLowerCase())))
    : rows;

  const exportCSV = () => {
    const csv = [columns.join(','), ...rows.map((r) => r.map((v) => `"${v}"`).join(','))].join('\n');
    const a = document.createElement('a');
    a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv);
    a.download = 'text2sql_results.csv';
    a.click();
  };

  return (
    <div className="card p-5 fade-in">
      {/* Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-2">
          <TableIcon className="w-4 h-4 text-indigo-500" />
          <h3 className="text-sm font-semibold text-slate-800">Query Results</h3>
          <span className="pill pill-slate">
            {rowCount ?? filteredRows.length} rows
            {truncated && ' (capped at 100)'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-400 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Filter results…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-xs rounded-lg border border-slate-200 bg-white focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 outline-none text-slate-700"
            />
          </div>
          <button
            onClick={exportCSV}
            className="btn-secondary flex items-center gap-1.5 !py-1.5 !px-3 !text-xs"
          >
            <Download className="w-3.5 h-3.5 text-indigo-500" />
            Export CSV
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto rounded-xl border border-slate-200 max-h-96">
        <table className="w-full text-left data-table">
          <thead>
            <tr>
              {columns.map((col, i) => (
                <th key={i}>{col}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredRows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} className="text-center py-6 text-slate-400 text-sm !font-sans">
                  No rows match your filter.
                </td>
              </tr>
            ) : (
              filteredRows.map((row, ri) => (
                <tr key={ri}>
                  {row.map((cell, ci) => (
                    <td key={ci}>
                      {cell === null
                        ? <span className="text-slate-300 italic text-xs">NULL</span>
                        : String(cell)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
