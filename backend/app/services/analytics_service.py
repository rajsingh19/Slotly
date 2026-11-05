from typing import Dict, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.call_session import CallSession
from app.schemas.analytics import AnalyticsOut, DoctorWorkload


class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_analytics(self) -> AnalyticsOut:
        # Total appointments
        total_appts_res = await self.db.execute(select(func.count(Appointment.id)))
        total_appointments = total_appts_res.scalar() or 0

        # Appointments by status
        status_stmt = select(Appointment.status, func.count(Appointment.id)).group_by(Appointment.status)
        status_res = await self.db.execute(status_stmt)
        status_counts: Dict[str, int] = {row[0]: row[1] for row in status_res.all()}

        # Total patients
        patients_res = await self.db.execute(select(func.count(Patient.id)))
        total_patients = patients_res.scalar() or 0

        # Total doctors
        doctors_res = await self.db.execute(select(func.count(Doctor.id)))
        total_doctors = doctors_res.scalar() or 0

        # Calls aggregates
        calls_stmt = select(
            func.count(CallSession.id),
            func.coalesce(func.sum(CallSession.duration_seconds), 0),
            func.coalesce(func.avg(CallSession.duration_seconds), 0.0),
            func.coalesce(func.sum(CallSession.estimated_cost), 0.0)
        )
        calls_res = await self.db.execute(calls_stmt)
        total_calls, total_duration, avg_duration, total_cost = calls_res.first() or (0, 0, 0.0, 0.0)

        # Doctor workload breakdown
        workload_stmt = (
            select(
                Doctor.id,
                Doctor.name,
                Doctor.specialization,
                func.count(Appointment.id)
            )
            .outerjoin(Appointment, Doctor.id == Appointment.doctor_id)
            .group_by(Doctor.id, Doctor.name, Doctor.specialization)
            .order_by(func.count(Appointment.id).desc())
        )
        workload_res = await self.db.execute(workload_stmt)
        workloads = [
            DoctorWorkload(
                doctor_id=row[0],
                doctor_name=row[1],
                specialization=row[2],
                appointments_count=row[3],
            )
            for row in workload_res.all()
        ]

        return AnalyticsOut(
            total_appointments=total_appointments,
            appointments_by_status=status_counts,
            total_patients=total_patients,
            total_doctors=total_doctors,
            total_calls=total_calls,
            total_call_duration_seconds=int(total_duration),
            average_call_duration_seconds=round(float(avg_duration), 2),
            total_estimated_cost=round(float(total_cost), 2),
            doctor_workload=workloads,
        )
