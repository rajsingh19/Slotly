from typing import Dict, List, Any
from pydantic import BaseModel


class DoctorWorkload(BaseModel):
    doctor_id: int
    doctor_name: str
    specialization: str
    appointments_count: int


class AnalyticsOut(BaseModel):
    total_appointments: int
    appointments_by_status: Dict[str, int]
    total_patients: int
    total_doctors: int
    total_calls: int
    total_call_duration_seconds: int
    average_call_duration_seconds: float
    total_estimated_cost: float
    doctor_workload: List[DoctorWorkload]

