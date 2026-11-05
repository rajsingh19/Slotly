import React, { useState, useEffect } from 'react';
import { Stethoscope, Calendar, Clock, DollarSign, MapPin, Search } from 'lucide-react';
import { Doctor, TimeSlot } from '../types';
import { api } from '../services/api';

interface DoctorsListProps {
  onSelectSlotToBook?: (doctor: Doctor, slot: TimeSlot) => void;
}

export const DoctorsList: React.FC<DoctorsListProps> = ({ onSelectSlotToBook }) => {
  const [doctors, setDoctors] = useState<Doctor[]>([]);
  const [selectedSpecialty, setSelectedSpecialty] = useState<string>('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [activeDoctorSlots, setActiveDoctorSlots] = useState<{ doctorId: number; slots: TimeSlot[] } | null>(null);

  const specialties = ['All', 'Cardiology', 'Pediatrics', 'Orthopedics', 'Neurology', 'General Medicine', 'Dermatology'];

  useEffect(() => {
    loadDoctors();
  }, [selectedSpecialty]);

  const loadDoctors = async () => {
    setLoading(true);
    try {
      const data = await api.getDoctors(selectedSpecialty === 'All' ? undefined : selectedSpecialty);
      setDoctors(data);
    } catch (e) {
      console.error('Failed to load doctors:', e);
    } finally {
      setLoading(false);
    }
  };

  const handleViewSlots = async (doctor: Doctor) => {
    try {
      const slots = await api.getAvailableSlots(doctor.specialty);
      const docSlots = slots.filter(s => s.doctor_id === doctor.id);
      setActiveDoctorSlots({ doctorId: doctor.id, slots: docSlots });
    } catch (e) {
      console.error('Failed to fetch slots:', e);
    }
  };

  const filteredDoctors = doctors.filter(d =>
    d.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    d.specialty.toLowerCase().includes(searchQuery.toLowerCase()) ||
    d.qualification.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="flex flex-col gap-6">
      {/* Filters and Search Bar */}
      <div className="flex flex-col md:flex-row items-center justify-between gap-4 bg-slate-900 border border-slate-800 p-4 rounded-2xl">
        {/* Specialty Filter Chips */}
        <div className="flex items-center gap-1.5 overflow-x-auto w-full md:w-auto pb-2 md:pb-0">
          {specialties.map(spec => (
            <button
              key={spec}
              onClick={() => setSelectedSpecialty(spec)}
              className={`px-3 py-1.5 rounded-xl text-xs font-medium whitespace-nowrap transition-colors ${
                selectedSpecialty === spec
                  ? 'bg-sky-500 text-white shadow-md shadow-sky-500/20'
                  : 'bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white'
              }`}
            >
              {spec}
            </button>
          ))}
        </div>

        {/* Search */}
        <div className="relative w-full md:w-64">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search doctors..."
            className="w-full bg-slate-950 border border-slate-700 rounded-xl pl-9 pr-3 py-1.5 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-sky-500"
          />
        </div>
      </div>

      {/* Doctors Grid */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {[1, 2, 3, 4, 5, 6].map(i => (
            <div key={i} className="h-64 bg-slate-900/50 border border-slate-800 rounded-2xl animate-pulse" />
          ))}
        </div>
      ) : filteredDoctors.length === 0 ? (
        <div className="text-center py-12 bg-slate-900 border border-slate-800 rounded-2xl">
          <Stethoscope className="w-10 h-10 text-slate-600 mx-auto mb-2" />
          <p className="text-slate-400 text-sm">No doctors found matching your filter criteria.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {filteredDoctors.map(doctor => (
            <div
              key={doctor.id}
              className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-2xl p-5 shadow-lg flex flex-col justify-between transition-all"
            >
              <div>
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400 flex items-center justify-center font-bold text-lg">
                      {doctor.name.replace('Dr. ', '').charAt(0)}
                    </div>
                    <div>
                      <h4 className="font-semibold text-white text-base">{doctor.name}</h4>
                      <span className="text-xs font-medium text-sky-400 bg-sky-500/10 px-2 py-0.5 rounded-md">
                        {doctor.specialty}
                      </span>
                    </div>
                  </div>
                </div>

                <p className="text-xs text-slate-400 mt-3 font-mono">
                  {doctor.qualification}
                </p>

                <div className="mt-4 pt-4 border-t border-slate-800/80 space-y-2 text-xs text-slate-300">
                  <div className="flex items-center gap-2">
                    <MapPin className="w-3.5 h-3.5 text-slate-400" />
                    <span>{doctor.room_number} • {doctor.department}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Clock className="w-3.5 h-3.5 text-slate-400" />
                    <span>{doctor.start_time} - {doctor.end_time} ({doctor.available_days})</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <DollarSign className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Consultation Fee: <strong>${doctor.consultation_fee}</strong></span>
                  </div>
                </div>
              </div>

              {/* View Available Slots Action */}
              <div className="mt-5 pt-3 border-t border-slate-800">
                <button
                  onClick={() => handleViewSlots(doctor)}
                  className="w-full py-2 px-3 rounded-xl bg-slate-800 hover:bg-slate-700 text-sky-300 hover:text-white text-xs font-medium flex items-center justify-center gap-1.5 transition-colors"
                >
                  <Calendar className="w-3.5 h-3.5" />
                  <span>View Available Slots</span>
                </button>
              </div>

              {/* In-Card Slots Popover */}
              {activeDoctorSlots?.doctorId === doctor.id && (
                <div className="mt-4 p-3 bg-slate-950 border border-slate-800 rounded-xl space-y-2">
                  <div className="flex items-center justify-between text-xs font-medium text-slate-300">
                    <span>Next Open Slots:</span>
                    <button
                      onClick={() => setActiveDoctorSlots(null)}
                      className="text-slate-500 hover:text-white text-xs"
                    >
                      ✕
                    </button>
                  </div>
                  <div className="grid grid-cols-2 gap-1.5 max-h-36 overflow-y-auto pr-1">
                    {activeDoctorSlots.slots.slice(0, 8).map(slot => (
                      <button
                        key={slot.id}
                        onClick={() => onSelectSlotToBook?.(doctor, slot)}
                        className="p-1.5 rounded-lg bg-slate-900 border border-slate-800 hover:border-emerald-500/50 hover:bg-emerald-950/20 text-slate-300 hover:text-emerald-300 text-[11px] text-center transition-all"
                      >
                        <div>{slot.slot_date}</div>
                        <div className="font-mono text-[10px] text-slate-400">{slot.start_time}</div>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
