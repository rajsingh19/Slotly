import React from 'react';
import { PhoneCall, ShieldAlert, Activity, Settings, HeartPulse } from 'lucide-react';
import { HealthStatus, HospitalSummary } from '../types';

interface HeaderProps {
  summary: HospitalSummary | null;
  health: HealthStatus | null;
  onOpenSettings: () => void;
}

export const Header: React.FC<HeaderProps> = ({ summary, health, onOpenSettings }) => {
  return (
    <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-md sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          {/* Brand */}
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-sky-500 to-indigo-600 flex items-center justify-center shadow-lg shadow-sky-500/20">
              <HeartPulse className="w-6 h-6 text-white" />
            </div>
            <div>
              <h1 className="font-bold text-lg text-white leading-tight">
                {summary?.name || 'Apex Multi-Specialty Hospital'}
              </h1>
              <p className="text-xs text-slate-400 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                AI Receptionist & Voice Booking Agent
              </p>
            </div>
          </div>

          {/* Emergency Helpline & Quick Status */}
          <div className="flex items-center gap-3">
            <div className="hidden md:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-red-950/60 border border-red-800/60 text-red-300 text-xs font-medium">
              <ShieldAlert className="w-4 h-4 text-red-400" />
              <span>ER 24/7: <strong>{summary?.emergency_phone || '911'}</strong></span>
            </div>

            <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-slate-300 text-xs">
              <PhoneCall className="w-3.5 h-3.5 text-sky-400" />
              <span>Reception: {summary?.phone || '+1-800-555-0199'}</span>
            </div>

            {/* System Health Pill */}
            <div className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800/80 border border-slate-700/80 text-xs text-slate-300">
              <Activity className="w-3.5 h-3.5 text-emerald-400" />
              <span className="capitalize">{health?.database === 'healthy' ? 'System Online' : 'Degraded'}</span>
            </div>

            <button
              onClick={onOpenSettings}
              className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
              title="Voice & AI Settings"
            >
              <Settings className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </header>
  );
};
