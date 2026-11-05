export interface Doctor {
  id: number;
  name: string;
  specialty: string;
  department: string;
  qualification: string;
  consultation_fee: number;
  room_number: string;
  available_days: string;
  start_time: string;
  end_time: string;
  is_active: boolean;
}

export interface TimeSlot {
  id: number;
  doctor_id: number;
  slot_date: string;
  start_time: string;
  end_time: string;
  is_booked: boolean;
}

export interface Appointment {
  id: number;
  appointment_number: string;
  patient_name: string;
  patient_phone: string;
  patient_email?: string;
  patient_age?: number;
  patient_gender?: string;
  doctor_id: number;
  slot_id?: number;
  appointment_date: string;
  appointment_time: string;
  status: 'CONFIRMED' | 'RESCHEDULED' | 'CANCELLED' | 'COMPLETED';
  reason_for_visit?: string;
  notes?: string;
  created_at: string;
  updated_at: string;
  doctor?: Doctor;
}

export interface Department {
  id: number;
  name: string;
  description: string;
  floor: string;
  contact_extension: string;
  is_active: boolean;
}

export interface HospitalFAQ {
  id: number;
  category: string;
  question: string;
  answer: string;
  keywords?: string;
  is_active: boolean;
}

export interface HospitalSummary {
  name: string;
  phone: string;
  address: string;
  emergency_phone: string;
  visiting_hours: string;
  departments_count: number;
  doctors_count: number;
}

export interface HealthStatus {
  status: string;
  version: string;
  environment: string;
  database: string;
  cache: string;
  voice_stt: string;
  voice_tts: string;
  llm_provider: string;
  uptime_seconds: number;
}

export interface VoiceTranscriptMessage {
  id: string;
  speaker: 'user' | 'assistant' | 'system';
  message: string;
  timestamp: string;
  latency_ms?: number;
  action_type?: string;
  action_payload?: any;
}
