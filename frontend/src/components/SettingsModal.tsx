import React from 'react';
import { Settings as SettingsIcon, CheckCircle2, Cpu, Mic, Volume2, Database, ShieldCheck } from 'lucide-react';
import { HealthStatus } from '../types';

interface SettingsModalProps {
  isOpen: boolean;
  onClose: () => void;
  health: HealthStatus | null;
}

export const SettingsModal: React.FC<SettingsModalProps> = ({ isOpen, onClose, health }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-5">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <SettingsIcon className="w-4 h-4 text-sky-400" />
            <h3 className="font-semibold text-white text-base">AI & Voice Stack Architecture</h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-white text-sm">✕</button>
        </div>

        <div className="space-y-3 text-xs">
          <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Mic className="w-4 h-4 text-sky-400" />
              <div>
                <p className="font-medium text-slate-200">Speech-to-Text (STT)</p>
                <p className="text-slate-500 text-[11px]">Sarvam AI (saarika:v2) & Web Audio</p>
              </div>
            </div>
            <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-mono text-[11px]">
              {health?.voice_stt || 'Ready'}
            </span>
          </div>

          <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Volume2 className="w-4 h-4 text-indigo-400" />
              <div>
                <p className="font-medium text-slate-200">Text-to-Speech (TTS)</p>
                <p className="text-slate-500 text-[11px]">Sarvam AI Bulbul (bulbul:v1, speaker: ananya)</p>
              </div>
            </div>
            <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-mono text-[11px]">
              {health?.voice_tts || 'Ready'}
            </span>
          </div>

          <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Cpu className="w-4 h-4 text-amber-400" />
              <div>
                <p className="font-medium text-slate-200">LLM Provider & Dialogue</p>
                <p className="text-slate-500 text-[11px]">Configurable Abstraction Layer (Mock / Gemini / OpenAI)</p>
              </div>
            </div>
            <span className="px-2 py-0.5 rounded-full bg-sky-500/10 text-sky-400 font-mono text-[11px]">
              {health?.llm_provider || 'Mock Engine'}
            </span>
          </div>

          <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <Database className="w-4 h-4 text-emerald-400" />
              <div>
                <p className="font-medium text-slate-200">Database & Persistence</p>
                <p className="text-slate-500 text-[11px]">PostgreSQL with SQLite local dev fallback</p>
              </div>
            </div>
            <span className="px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-mono text-[11px]">
              {health?.database || 'Healthy'}
            </span>
          </div>

          <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <ShieldCheck className="w-4 h-4 text-purple-400" />
              <div>
                <p className="font-medium text-slate-200">System Uptime & Environment</p>
                <p className="text-slate-500 text-[11px]">{health?.environment || 'development'} • v{health?.version || '1.0.0'}</p>
              </div>
            </div>
            <span className="font-mono text-slate-400 text-[11px]">
              {health ? `${Math.round(health.uptime_seconds)}s uptime` : 'Active'}
            </span>
          </div>
        </div>

        <div className="pt-2 flex justify-end">
          <button
            onClick={onClose}
            className="py-1.5 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs text-white"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
