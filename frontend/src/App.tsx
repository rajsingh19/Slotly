import React, { useState, useEffect } from 'react';
import { PhoneCall, Calendar, Users, HelpCircle } from 'lucide-react';
import { Header } from './components/Header';
import { VoiceConsole } from './components/VoiceConsole';
import { DoctorsList } from './components/DoctorsList';
import { AppointmentsView } from './components/AppointmentsView';
import { HospitalInfo } from './components/HospitalInfo';
import { SettingsModal } from './components/SettingsModal';
import { HospitalSummary, HealthStatus, Doctor, TimeSlot } from './types';
import { api } from './services/api';

type Tab = 'voice' | 'doctors' | 'appointments' | 'hospital';

export function App() {
  const [activeTab, setActiveTab] = useState<Tab>('voice');
  const [summary, setSummary] = useState<HospitalSummary | null>(null);
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [appointmentRefreshTrigger, setAppointmentRefreshTrigger] = useState(0);

  useEffect(() => {
    loadAppData();
    const interval = setInterval(loadAppData, 30000);
    return () => clearInterval(interval);
  }, []);

  const loadAppData = async () => {
    try {
      const [sum, h] = await Promise.all([
        api.getHospitalSummary(),
        api.getHealth(),
      ]);
      setSummary(sum);
      setHealth(h);
    } catch (e) {
      console.warn('Backend not yet reachable:', e);
    }
  };

  const handleAppointmentUpdated = () => {
    setAppointmentRefreshTrigger(prev => prev + 1);
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col">
      <Header
        summary={summary}
        health={health}
        onOpenSettings={() => setIsSettingsOpen(true)}
      />

      {/* Main Navigation Bar */}
      <div className="border-b border-slate-800 bg-slate-900/40">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <nav className="flex space-x-2 sm:space-x-4 py-2.5 overflow-x-auto">
            <button
              onClick={() => setActiveTab('voice')}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs sm:text-sm font-medium transition-all ${
                activeTab === 'voice'
                  ? 'bg-sky-500/10 text-sky-400 border border-sky-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              }`}
            >
              <PhoneCall className="w-4 h-4 text-sky-400" />
              <span>AI Reception Voice Agent</span>
            </button>

            <button
              onClick={() => setActiveTab('doctors')}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs sm:text-sm font-medium transition-all ${
                activeTab === 'doctors'
                  ? 'bg-sky-500/10 text-sky-400 border border-sky-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              }`}
            >
              <Users className="w-4 h-4 text-indigo-400" />
              <span>Doctor Directory & Schedules</span>
            </button>

            <button
              onClick={() => setActiveTab('appointments')}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs sm:text-sm font-medium transition-all ${
                activeTab === 'appointments'
                  ? 'bg-sky-500/10 text-sky-400 border border-sky-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              }`}
            >
              <Calendar className="w-4 h-4 text-emerald-400" />
              <span>Appointments Management</span>
            </button>

            <button
              onClick={() => setActiveTab('hospital')}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs sm:text-sm font-medium transition-all ${
                activeTab === 'hospital'
                  ? 'bg-sky-500/10 text-sky-400 border border-sky-500/30 shadow-sm'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
              }`}
            >
              <HelpCircle className="w-4 h-4 text-purple-400" />
              <span>Hospital Knowledge & FAQs</span>
            </button>
          </nav>
        </div>
      </div>

      {/* Main Content Area */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'voice' && (
          <VoiceConsole onAppointmentUpdated={handleAppointmentUpdated} />
        )}
        {activeTab === 'doctors' && (
          <DoctorsList
            onSelectSlotToBook={(doc, slot) => {
              setActiveTab('voice');
            }}
          />
        )}
        {activeTab === 'appointments' && (
          <AppointmentsView refreshTrigger={appointmentRefreshTrigger} />
        )}
        {activeTab === 'hospital' && (
          <HospitalInfo summary={summary} />
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-800/80 bg-slate-900/40 py-4 text-center text-xs text-slate-500">
        <p>
          {summary?.name || 'Apex Hospital'} • Production-oriented MVP AI Voice System • Voice Orchestration: Pipecat Architecture • STT & Bulbul TTS: Sarvam AI
        </p>
      </footer>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        health={health}
      />
    </div>
  );
}

export default App;
