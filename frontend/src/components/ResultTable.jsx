import React, { useState } from 'react';
import { Table as TableIcon, Download, Search, AlertCircle } from 'lucide-react';

export default function ResultTable({ columns, rows, rowCount, truncated }) {
  const [filter, setFilter] = useState('');

  if (!columns || columns.length === 0) {
    return (
      <div className="glass-card rounded-2xl p-8 text-center text-slate-400 border border-slate-800/80">
        <AlertCircle className="w-8 h-8 text-slate-600 mx-auto mb-2" />
        <p className="text-sm">Query returned no rows or column schema available.</p>
      </div>
    );
  }

  const filteredRows = rows.filter((row) =>
    row.some((val) => String(val).toLowerCase().includes(filter.toLowerCase()))
  );

  const exportCSV = () => {
    const csvContent =
      'data:text/csv;charset=utf-8,' +
      [columns.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement('a');
    link.setAttribute('href', encodedUri);
    link.setAttribute('download', 'text2sql_results.csv');
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="glass-card rounded-2xl p-5 border border-slate-800/80 space-y-4">
      {/* Header & Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center space-x-2">
          <TableIcon className="w-5 h-5 text-indigo-400" />
          <h3 className="text-base font-semibold text-slate-100">Query Results</h3>
          <span className="text-xs px-2.5 py-0.5 rounded-full bg-slate-800 text-slate-300 font-mono">
            {rowCount} Rows {truncated && '(Truncated to Max Limit)'}
          </span>
        </div>

        <div className="flex items-center space-x-3">
          {/* Search Filter */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Filter results..."
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              className="pl-8 pr-3 py-1.5 rounded-lg bg-slate-950 border border-slate-800 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <button
            onClick={exportCSV}
            className="flex items-center space-x-1 text-xs px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium border border-slate-700 transition-colors"
          >
            <Download className="w-3.5 h-3.5 text-indigo-400" />
            <span>Export CSV</span>
          </button>
        </div>
      </div>

      {/* Table Data Grid */}
      <div className="overflow-x-auto rounded-xl border border-slate-800/80 max-h-96">
        <table className="w-full text-left text-xs text-slate-200">
          <thead className="bg-slate-900/90 text-slate-400 font-mono border-b border-slate-800 uppercase tracking-wider sticky top-0 backdrop-blur-md">
            <tr>
              {columns.map((col, idx) => (
                <th key={idx} className="px-4 py-3 font-semibold">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/50 bg-slate-950/40">
            {filteredRows.map((row, rIdx) => (
              <tr key={rIdx} className="hover:bg-slate-900/60 transition-colors">
                {row.map((cell, cIdx) => (
                  <td key={cIdx} className="px-4 py-2.5 font-mono text-slate-300">
                    {cell === null ? (
                      <span className="text-slate-600 italic">NULL</span>
                    ) : (
                      String(cell)
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
