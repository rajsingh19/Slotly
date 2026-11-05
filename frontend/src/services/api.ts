import { Doctor, TimeSlot, Appointment, Department, HospitalFAQ, HospitalSummary, HealthStatus } from '../types';

const API_BASE = '/api/v1';

async function fetchJSON<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  });

  const body = await res.json();
  if (!res.ok || body.success === false) {
    throw new Error(body.detail || body.message || 'API request failed');
  }
  return body.data;
}

export const api = {
  // Health
  getHealth: () => fetchJSON<HealthStatus>(`${API_BASE}/health`),

  // Hospital
  getHospitalSummary: () => fetchJSON<HospitalSummary>(`${API_BASE}/hospital/summary`),
  getDepartments: () => fetchJSON<Department[]>(`${API_BASE}/hospital/departments`),
  getFAQs: (query?: string) =>
    fetchJSON<HospitalFAQ[]>(`${API_BASE}/hospital/faqs${query ? `?query=${encodeURIComponent(query)}` : ''}`),

  // Doctors
  getDoctors: (specialty?: string) =>
    fetchJSON<Doctor[]>(`${API_BASE}/doctors${specialty ? `?specialty=${encodeURIComponent(specialty)}` : ''}`),
  getAvailableSlots: (specialty?: string, date?: string) => {
    const params = new URLSearchParams();
    if (specialty) params.append('specialty', specialty);
    if (date) params.append('target_date', date);
    return fetchJSON<TimeSlot[]>(`${API_BASE}/doctors/slots/available?${params.toString()}`);
  },

  // Appointments
  getAppointments: (phone?: string) =>
    fetchJSON<Appointment[]>(`${API_BASE}/appointments${phone ? `?phone=${encodeURIComponent(phone)}` : ''}`),
  bookAppointment: (payload: {
    patient_name: string;
    patient_phone: string;
    patient_email?: string;
    doctor_id: number;
    slot_id: number;
    reason_for_visit?: string;
  }) => fetchJSON<Appointment>(`${API_BASE}/appointments`, {
    method: 'POST',
    body: JSON.stringify(payload),
  }),
  rescheduleAppointment: (identifier: string, newSlotId: number, reason?: string) =>
    fetchJSON<Appointment>(`${API_BASE}/appointments/${encodeURIComponent(identifier)}/reschedule`, {
      method: 'PATCH',
      body: JSON.stringify({ new_slot_id: newSlotId, reason }),
    }),
  cancelAppointment: (identifier: string, reason?: string) =>
    fetchJSON<Appointment>(`${API_BASE}/appointments/${encodeURIComponent(identifier)}/cancel`, {
      method: 'PATCH',
      body: JSON.stringify({ cancellation_reason: reason }),
    }),

  // Voice
  createVoiceSession: (callerPhone?: string) =>
    fetchJSON<{ session_id: string; welcome_message: string; ws_url: string }>(`${API_BASE}/voice/session`, {
      method: 'POST',
      body: JSON.stringify({ caller_phone: callerPhone }),
    }),
  simulateTurn: (sessionId: string, message: string) =>
    fetchJSON<{ session_id: string; user_message: string; assistant_reply: string }>(
      `${API_BASE}/voice/simulate-turn?session_id=${encodeURIComponent(sessionId)}&message=${encodeURIComponent(message)}`,
      { method: 'POST' }
    ),
  getCallLogs: () => fetchJSON<any[]>(`${API_BASE}/voice/calls`),
};
