import React, { useState } from 'react';
import { MessageSquare, Sparkles, Send, Play, Terminal } from 'lucide-react';

const SAMPLE_QUESTIONS = {
  concert_singer: [
    "How many singers are there in total and what is their average age?",
    "Which stadium has hosted the most concerts?",
    "List the names of singers sorted by age in descending order."
  ],
  student_assessment: [
    "Which course has the most number of registered students?",
    "What are the ids of students registered in the least number of courses?",
    "List the first name and last name of all candidates."
  ],
  pets_1: [
    "What are the first names of students who own a cat?",
    "Find the average weight of pets by pet type.",
    "Which student owns the oldest pet?"
  ]
};

export default function QueryWorkspace({ selectedDb, onExecute, loading }) {
  const [question, setQuestion] = useState(
    "How many singers are there in total and what is their average age?"
  );

  const presets = SAMPLE_QUESTIONS[selectedDb] || SAMPLE_QUESTIONS.concert_singer;

  const handleSubmit = (e) => {
    e.preventDefault();
    if (question.trim()) {
      onExecute(question);
    }
  };

  return (
    <div className="glass-card rounded-2xl p-5 border border-slate-800/80">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center space-x-2">
          <MessageSquare className="w-5 h-5 text-indigo-400" />
          <h2 className="text-base font-semibold text-slate-100">Natural Language Prompt</h2>
        </div>
        <span className="text-xs text-slate-400 flex items-center gap-1 font-mono">
          <Terminal className="w-3.5 h-3.5 text-indigo-400" /> Target DB: {selectedDb}
        </span>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="relative">
          <textarea
            rows={3}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask a question in plain English (e.g. 'Show top 5 courses by registration count')..."
            className="w-full rounded-xl bg-slate-950/70 border border-slate-800/90 p-4 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-indigo-500/80 focus:ring-1 focus:ring-indigo-500/50 resize-none font-sans"
          />
        </div>

        {/* Example Presets */}
        <div>
          <span className="text-xs text-slate-400 font-medium flex items-center gap-1 mb-2">
            <Sparkles className="w-3.5 h-3.5 text-amber-400" /> Quick Preset Questions:
          </span>
          <div className="flex flex-wrap gap-2">
            {presets.map((preset, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => setQuestion(preset)}
                className="text-xs px-3 py-1.5 rounded-lg bg-slate-900/80 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 text-slate-300 transition-all text-left truncate max-w-xs"
              >
                "{preset}"
              </button>
            ))}
          </div>
        </div>

        {/* Submit Button */}
        <div className="flex justify-end pt-2">
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className={`flex items-center space-x-2 px-6 py-2.5 rounded-xl font-semibold text-sm text-white transition-all shadow-lg ${
              loading || !question.trim()
                ? 'bg-slate-800 text-slate-500 cursor-not-allowed'
                : 'bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 shadow-indigo-600/30 hover:scale-[1.01]'
            }`}
          >
            {loading ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Generating & Validating...</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-current" />
                <span>Generate & Execute SQL</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
