import React, { useState } from 'react';
import { MessageSquare, Sparkles, Play, Terminal, Loader2 } from 'lucide-react';

const SAMPLE_QUESTIONS = {
  chinook_1: [
    'How many artists are in the database?',
    'List the top 5 longest tracks.',
    'Count the number of customers from Brazil.',
    'DROP TABLE Track;',
    'SELECT * FROM sqlite_master;',
  ],
  concert_singer: [
    'How many singers are there in total and what is their average age?',
    'Which stadium has hosted the most concerts?',
    'List the names of singers sorted by age descending.',
  ],
  student_assessment: [
    'Which course has the most number of registered students?',
    'What are the ids of students registered in the least number of courses?',
    'List the first name and last name of all candidates.',
  ],
  pets_1: [
    'What are the first names of students who own a cat?',
    'Find the average weight of pets by type.',
    'Which student owns the oldest pet?',
  ],
};

export default function QueryWorkspace({ selectedDb, onExecute, loading }) {
  const [question, setQuestion] = useState(
    'How many singers are there in total and what is their average age?'
  );

  const presets = SAMPLE_QUESTIONS[selectedDb] || [];

  const handleSubmit = (e) => {
    e.preventDefault();
    if (question.trim() && !loading) onExecute(question);
  };

  return (
    <div className="card p-5 fade-in">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <MessageSquare className="w-4.5 h-4.5 text-indigo-500" />
          <h2 className="text-sm font-semibold text-slate-800">Natural Language Query</h2>
        </div>
        <span className="text-xs text-slate-400 flex items-center gap-1 font-mono">
          <Terminal className="w-3.5 h-3.5 text-slate-400" />
          {selectedDb || 'no db selected'}
        </span>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <textarea
          rows={3}
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask a question in plain English, e.g. 'Show all albums released after 2010'…"
          className="input-field resize-none text-sm"
        />

        {/* Preset chips */}
        {presets.length > 0 && (
          <div>
            <p className="text-[11px] text-slate-500 font-medium flex items-center gap-1 mb-2">
              <Sparkles className="w-3 h-3 text-amber-400" /> Sample questions:
            </p>
            <div className="flex flex-wrap gap-1.5">
              {presets.map((p, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => setQuestion(p)}
                  className="text-[11px] px-3 py-1.5 rounded-lg bg-slate-100 hover:bg-indigo-50 hover:text-indigo-700 border border-slate-200 hover:border-indigo-200 text-slate-600 transition-all truncate max-w-[240px]"
                  title={p}
                >
                  "{p}"
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={loading || !question.trim() || !selectedDb}
            className="btn-primary flex items-center gap-2"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                Generating & Validating…
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-current" />
                Generate & Execute SQL
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
