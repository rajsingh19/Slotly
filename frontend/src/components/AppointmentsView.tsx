import React, { useState, useEffect } from 'react';
import {
  Calendar,
  Clock,
  User,
  Phone,
  FileText,
  Search,
  CheckCircle,
  XCircle,
  RefreshCw,
  AlertCircle
} from 'lucide-react';
import { Appointment, TimeSlot } from '../types';
import { api } from '../services/api';

interface AppointmentsViewProps {
  refreshTrigger?: number;
}

export const AppointmentsView: React.FC<AppointmentsViewProps> = ({ refreshTrigger }) => {
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchPhone, setSearchPhone] = useState('');
  const [reschedulingApt, setReschedulingApt] = useState<Appointment | null>(null);
  const [availableSlots, setAvailableSlots] = useState<TimeSlot[]>([]);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  useEffect(() => {
    loadAppointments();
  }, [refreshTrigger]);

  const loadAppointments = async (phone?: string) => {
    setLoading(true);
    try {
      const data = await api.getAppointments(phone);
      setAppointments(data);
    } catch (e) {
      console.error('Failed to load appointments:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    loadAppointments(searchPhone.trim() || undefined);
  };

  const handleCancel = async (apt: Appointment) => {
    if (!window.confirm(`Are you sure you want to cancel appointment ${apt.appointment_number}?`)) return;
    try {
      await api.cancelAppointment(apt.appointment_number, 'Patient requested cancellation in dashboard');
      setActionMessage(`Appointment ${apt.appointment_number} cancelled.`);
      loadAppointments();
    } catch (e: any) {
      alert(`Error cancelling appointment: ${e.message}`);
    }
  };

  const handleStartReschedule = async (apt: Appointment) => {
    setReschedulingApt(apt);
    try {
      const slots = await api.getAvailableSlots(apt.doctor?.specialty);
      setAvailableSlots(slots);
    } catch (e) {
      console.error('Failed to load slots for reschedule:', e);
    }
  };

  const handleConfirmReschedule = async (newSlot: TimeSlot) => {
    if (!reschedulingApt) return;
    try {
      await api.rescheduleAppointment(
        reschedulingApt.appointment_number,
        newSlot.id,
        'Rescheduled via dashboard'
      );
      setActionMessage(`Appointment ${reschedulingApt.appointment_number} successfully moved to ${newSlot.slot_date} ${newSlot.start_time}`);
      setReschedulingApt(null);
      loadAppointments();
    } catch (e: any) {
      alert(`Error rescheduling: ${e.message}`);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Search Header */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 bg-slate-900 border border-slate-800 p-4 rounded-2xl">
        <form onSubmit={handleSearch} className="flex items-center gap-2 w-full sm:w-auto">
          <div className="relative flex-1 sm:w-72">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchPhone}
              onChange={(e) => setSearchPhone(e.target.value)}
              placeholder="Search by phone number..."
              className="w-full bg-slate-950 border border-slate-700 rounded-xl pl-9 pr-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500"
            />
          </div>
          <button
            type="submit"
            className="py-2 px-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs text-white font-medium"
          >
            Search
          </button>
          {searchPhone && (
            <button
              type="button"
              onClick={() => { setSearchPhone(''); loadAppointments(); }}
              className="py-2 px-2 text-xs text-slate-400 hover:text-white"
            >
              Reset
            </button>
          )}
        </form>

        <button
          onClick={() => loadAppointments()}
          className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-white py-2 px-3 rounded-xl bg-slate-800/60 hover:bg-slate-800 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Refresh</span>
        </button>
      </div>

      {actionMessage && (
        <div className="p-3 bg-sky-950/40 border border-sky-800/60 rounded-xl text-xs text-sky-300 flex items-center justify-between">
          <span>{actionMessage}</span>
          <button onClick={() => setActionMessage(null)} className="text-slate-400 hover:text-white">✕</button>
        </div>
      )}

      {/* Appointments List */}
      {loading ? (
        <div className="space-y-4">
          {[1, 2, 3].map(i => (
            <div key={i} className="h-28 bg-slate-900/50 border border-slate-800 rounded-2xl animate-pulse" />
          ))}
        </div>
      ) : appointments.length === 0 ? (
        <div className="text-center py-12 bg-slate-900 border border-slate-800 rounded-2xl">
          <Calendar className="w-10 h-10 text-slate-600 mx-auto mb-2" />
          <p className="text-slate-400 text-sm">No appointments found.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {appointments.map(apt => (
            <div
              key={apt.id}
              className="bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-lg flex flex-col md:flex-row md:items-center justify-between gap-4"
            >
              <div className="space-y-2">
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs font-semibold px-2.5 py-1 rounded-md bg-slate-800 text-slate-300 border border-slate-700">
                    {apt.appointment_number}
                  </span>

                  <span
                    className={`px-2.5 py-0.5 rounded-full text-[11px] font-medium ${
                      apt.status === 'CONFIRMED'
                        ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                        : apt.status === 'RESCHEDULED'
                        ? 'bg-sky-500/10 text-sky-400 border border-sky-500/20'
                        : 'bg-red-500/10 text-red-400 border border-red-500/20'
                    }`}
                  >
                    {apt.status}
                  </span>
                </div>

                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-300">
                  <span className="font-semibold text-sm text-white flex items-center gap-1.5">
                    <User className="w-3.5 h-3.5 text-sky-400" />
                    {apt.patient_name}
                  </span>
                  <span className="text-slate-400 flex items-center gap-1">
                    <Phone className="w-3 h-3" />
                    {apt.patient_phone}
                  </span>
                  <span className="text-slate-400 flex items-center gap-1">
                    <Calendar className="w-3 h-3 text-sky-400" />
                    {apt.appointment_date}
                  </span>
                  <span className="text-slate-400 flex items-center gap-1">
                    <Clock className="w-3 h-3 text-amber-400" />
                    {apt.appointment_time}
                  </span>
                </div>

                <div className="text-xs text-slate-400">
                  Doctor: <strong className="text-slate-200">{apt.doctor?.name || 'Assigned Physician'}</strong> ({apt.doctor?.specialty || 'General'}) • {apt.doctor?.room_number || 'Room 101'}
                </div>

                {apt.reason_for_visit && (
                  <div className="text-xs text-slate-500 italic">
                    Reason: {apt.reason_for_visit}
                  </div>
                )}
              </div>

              {/* Action Buttons */}
              {apt.status !== 'CANCELLED' && (
                <div className="flex items-center gap-2 pt-3 md:pt-0 border-t md:border-t-0 border-slate-800">
                  <button
                    onClick={() => handleStartReschedule(apt)}
                    className="py-1.5 px-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs text-sky-300 font-medium transition-colors"
                  >
                    Reschedule
                  </button>
                  <button
                    onClick={() => handleCancel(apt)}
                    className="py-1.5 px-3 rounded-xl bg-red-950/40 hover:bg-red-900/60 border border-red-800/60 text-xs text-red-300 font-medium transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Reschedule Modal */}
      {reschedulingApt && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-800 pb-3">
              <h3 className="font-semibold text-white text-sm">
                Reschedule {reschedulingApt.appointment_number}
              </h3>
              <button
                onClick={() => setReschedulingApt(null)}
                className="text-slate-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            <p className="text-xs text-slate-300">
              Select a new available time slot for <strong>{reschedulingApt.patient_name}</strong> with <strong>{reschedulingApt.doctor?.name}</strong>:
            </p>

            <div className="max-h-60 overflow-y-auto grid grid-cols-2 gap-2 pr-1">
              {availableSlots.length === 0 ? (
                <p className="text-xs text-slate-500 col-span-2 text-center py-4">No alternative open slots found.</p>
              ) : (
                availableSlots.map(slot => (
                  <button
                    key={slot.id}
                    onClick={() => handleConfirmReschedule(slot)}
                    className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 hover:border-sky-500 hover:bg-sky-950/20 text-xs text-left transition-all"
                  >
                    <div className="font-medium text-white">{slot.slot_date}</div>
                    <div className="text-slate-400 font-mono text-[11px]">{slot.start_time} - {slot.end_time}</div>
                  </button>
                ))
              )}
            </div>

            <div className="pt-2 flex justify-end">
              <button
                onClick={() => setReschedulingApt(null)}
                className="py-1.5 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs text-white"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
