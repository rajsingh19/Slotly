import re
import json
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.patient import PatientCreate, validate_phone_format
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate
from app.services.doctor_service import DoctorService
from app.services.patient_service import PatientService
from app.services.appointment_service import AppointmentService
from app.repositories.hospital_repo import HospitalRepository

logger = get_logger(__name__)

# Medical specialty normalization map (Hindi, Hinglish, informal terms)
SPECIALTY_NORMALIZATION_MAP = {
    "skin": "Dermatology",
    "chamdi": "Dermatology",
    "twacha": "Dermatology",
    "dermatologist": "Dermatology",
    "dermatology": "Dermatology",
    "heart": "Cardiology",
    "dil": "Cardiology",
    "seena": "Cardiology",
    "cardiologist": "Cardiology",
    "cardiology": "Cardiology",
    "cardiac": "Cardiology",
    "bone": "Orthopedics",
    "bones": "Orthopedics",
    "haddi": "Orthopedics",
    "haddiyan": "Orthopedics",
    "joint": "Orthopedics",
    "joints": "Orthopedics",
    "ghutna": "Orthopedics",
    "orthopedic": "Orthopedics",
    "orthopedics": "Orthopedics",
    "orthopaedics": "Orthopedics",
    "child": "Pediatrics",
    "children": "Pediatrics",
    "bacha": "Pediatrics",
    "bachon": "Pediatrics",
    "pediatric": "Pediatrics",
    "pediatrics": "Pediatrics",
    "pediatrician": "Pediatrics",
    "brain": "Neurology",
    "dimag": "Neurology",
    "sar dard": "Neurology",
    "sir dard": "Neurology",
    "neuro": "Neurology",
    "neurologist": "Neurology",
    "neurology": "Neurology",
    "fever": "General Medicine",
    "cold": "General Medicine",
    "cough": "General Medicine",
    "khasi": "General Medicine",
    "bukhar": "General Medicine",
    "pet dard": "General Medicine",
    "general": "General Medicine",
    "general physician": "General Medicine",
    "general medicine": "General Medicine",
    "physician": "General Medicine",
}


def normalize_specialization(spec: str) -> str:
    cleaned = spec.lower().strip()
    return SPECIALTY_NORMALIZATION_MAP.get(cleaned, spec.title())


# =====================================================================
# Pydantic Input Schemas for Safe Argument Validation
# =====================================================================

class SearchDoctorsInput(BaseModel):
    specialization: str = Field(..., description="Doctor specialization or clinical department, e.g. Cardiology, Dermatology, Pediatrics, Orthopedics, Neurology, General Medicine")


class GetDoctorDetailsInput(BaseModel):
    doctor_id: int = Field(..., gt=0, description="Unique ID of the doctor")


class CheckAvailabilityInput(BaseModel):
    doctor_id: int = Field(..., gt=0, description="Unique ID of the doctor")
    date: str = Field(..., description="Target date in YYYY-MM-DD format (must not be in the past)")

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            parsed = date.fromisoformat(v.strip())
            if parsed < date.today():
                raise ValueError("Appointment date cannot be in the past.")
        except Exception as e:
            raise ValueError(f"Invalid date format (must be YYYY-MM-DD): {e}")
        return v.strip()


class RegisterPatientInput(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Full name of the patient")
    phone_number: str = Field(..., description="Contact phone number (10-15 digits)")

    @field_validator("phone_number")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return validate_phone_format(v)


class BookAppointmentInput(BaseModel):
    patient_id: int = Field(..., gt=0, description="Registered Patient ID")
    doctor_id: int = Field(..., gt=0, description="Doctor ID")
    date: str = Field(..., description="Appointment date in YYYY-MM-DD format")
    time: str = Field(..., description="Appointment time slot, e.g. 10:00, 11:30, 14:00")
    idempotency_key: Optional[str] = Field(None, description="Client idempotency key to prevent duplicate booking on retries")

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        try:
            parsed = date.fromisoformat(v.strip())
            if parsed < date.today():
                raise ValueError("Appointment date cannot be in the past.")
        except Exception as e:
            raise ValueError(f"Invalid date format: {e}")
        return v.strip()


class RescheduleAppointmentInput(BaseModel):
    appointment_id: int = Field(..., gt=0, description="Unique ID of the existing appointment")
    new_date: str = Field(..., description="New target date in YYYY-MM-DD format")
    new_time: str = Field(..., description="New target time slot, e.g. 11:00 or 15:00")


class CancelAppointmentInput(BaseModel):
    appointment_id: int = Field(..., gt=0, description="Unique ID of the appointment to cancel")
    confirmation: bool = Field(..., description="Explicit caller confirmation flag (must be True to execute cancellation)")


class GetHospitalInformationInput(BaseModel):
    query: str = Field(..., min_length=2, description="Topic or query, e.g. visiting hours, emergency services, address, insurance, contact")


class RequestHumanHandoffInput(BaseModel):
    reason: str = Field(..., description="Reason for escalating call to human staff")


# =====================================================================
# Safe Tool Registry
# =====================================================================

class SafeToolRegistry:
    """
    Central tool registry enforcing strict parameter validation,
    safety checks, and delegation only to verified service layers.
    Never exposes raw SQL or database internals to the LLM.
    """

    def __init__(self):
        # In-memory idempotency cache for booking operations: idempotency_key -> booking result
        self._idempotency_cache: Dict[str, Dict[str, Any]] = {}

    async def search_doctors(self, db: AsyncSession, args: SearchDoctorsInput) -> Dict[str, Any]:
        """Tool 1: Search active doctors matching specialization."""
        norm_spec = normalize_specialization(args.specialization)
        doctor_service = DoctorService(db)
        page_res = await doctor_service.list_doctors(specialization=norm_spec, is_active=True, page=1, size=10)
        
        # If none found by strict match, fallback to searching all active doctors if general inquiry
        doctors = page_res.items
        if not doctors and norm_spec != "General Medicine":
            # Try partial keyword match
            all_active = await doctor_service.list_doctors(is_active=True, page=1, size=20)
            doctors = [
                d for d in all_active.items 
                if norm_spec.lower() in d.specialization.lower() or d.specialization.lower() in norm_spec.lower()
            ]

        if not doctors:
            return {
                "status": "none_found",
                "specialization": norm_spec,
                "message": f"No active doctors found for {norm_spec}.",
                "doctors": [],
                "count": 0
            }

        formatted = [
            {
                "id": d.id,
                "name": d.name,
                "specialization": d.specialization,
                "consultation_fee": d.consultation_fee,
                "is_active": d.is_active,
            }
            for d in doctors
        ]
        return {
            "status": "success",
            "specialization": norm_spec,
            "doctors": formatted,
            "count": len(formatted),
        }

    async def get_doctor_details(self, db: AsyncSession, args: GetDoctorDetailsInput) -> Dict[str, Any]:
        """Tool 2: Get verified information about a doctor."""
        doctor_service = DoctorService(db)
        try:
            doc = await doctor_service.get_doctor_by_id(args.doctor_id)
            return {
                "status": "success",
                "doctor": {
                    "id": doc.id,
                    "name": doc.name,
                    "specialization": doc.specialization,
                    "consultation_fee": doc.consultation_fee,
                    "is_active": doc.is_active,
                }
            }
        except HTTPException as e:
            return {"status": "not_found", "message": e.detail}

    async def check_availability(self, db: AsyncSession, args: CheckAvailabilityInput) -> Dict[str, Any]:
        """Tool 3: Check available appointment slots for a doctor on a specific date."""
        target_date = date.fromisoformat(args.date)
        doctor_service = DoctorService(db)
        try:
            avail_list = await doctor_service.get_availability(doctor_id=args.doctor_id, target_date=target_date)
            if not avail_list:
                return {
                    "status": "not_found",
                    "doctor_id": args.doctor_id,
                    "date": args.date,
                    "message": "Doctor availability could not be retrieved.",
                    "available_slots": [],
                    "has_slots": False
                }

            doc_avail = avail_list[0]
            available_slots = [s.time for s in doc_avail.slots if s.is_available]
            return {
                "status": "success" if available_slots else "fully_booked",
                "doctor_id": args.doctor_id,
                "doctor_name": doc_avail.doctor_name,
                "specialization": doc_avail.specialization,
                "date": args.date,
                "available_slots": available_slots,
                "has_slots": len(available_slots) > 0,
                "message": f"{len(available_slots)} slots available on {args.date}." if available_slots else f"No slots available on {args.date}."
            }
        except HTTPException as e:
            return {"status": "error", "message": e.detail}

    async def register_patient(self, db: AsyncSession, args: RegisterPatientInput) -> Dict[str, Any]:
        """Tool 4: Register or resolve patient details."""
        patient_service = PatientService(db)
        try:
            patient = await patient_service.create_patient(
                PatientCreate(name=args.name, phone_number=args.phone_number)
            )
            return {
                "status": "success",
                "patient_id": patient.id,
                "name": patient.name,
                "phone_number": patient.phone_number,
            }
        except HTTPException as e:
            return {"status": "error", "message": e.detail}
        except Exception as e:
            return {"status": "error", "message": f"Patient registration failed: {str(e)}"}

    async def book_appointment(self, db: AsyncSession, args: BookAppointmentInput) -> Dict[str, Any]:
        """Tool 5: Book an appointment with idempotency and double-booking protection."""
        # 1. Idempotency check: if request was already executed, return cached result
        cache_key = args.idempotency_key or f"book_{args.patient_id}_{args.doctor_id}_{args.date}_{args.time}"
        if cache_key in self._idempotency_cache:
            logger.info(f"Returning cached booking response for idempotency key: {cache_key}")
            return self._idempotency_cache[cache_key]

        target_date = date.fromisoformat(args.date)
        appointment_service = AppointmentService(db)
        try:
            apt = await appointment_service.create_appointment(
                AppointmentCreate(
                    doctor_id=args.doctor_id,
                    patient_id=args.patient_id,
                    appointment_date=target_date,
                    appointment_time=args.time,
                )
            )

            result = {
                "status": "booked",
                "appointment_id": apt.id,
                "booking_reference": apt.booking_reference,
                "doctor_id": apt.doctor_id,
                "doctor_name": apt.doctor.name if apt.doctor else "",
                "specialization": apt.doctor.specialization if apt.doctor else "",
                "date": str(apt.appointment_date),
                "time": apt.appointment_time,
                "patient_id": apt.patient_id,
                "patient_name": apt.patient.name if apt.patient else "",
                "status_code": 201,
            }
            # Cache successful booking for idempotency
            self._idempotency_cache[cache_key] = result
            return result
        except HTTPException as he:
            return {
                "status": "conflict" if he.status_code == 409 else "error",
                "message": he.detail,
                "status_code": he.status_code,
            }
        except Exception as e:
            logger.error(f"Error booking appointment: {e}", exc_info=True)
            return {"status": "error", "message": "Failed to book appointment due to database error."}

    async def reschedule_appointment(self, db: AsyncSession, args: RescheduleAppointmentInput) -> Dict[str, Any]:
        """Tool 6: Reschedule an existing appointment to a new date and time."""
        target_date = date.fromisoformat(args.new_date)
        appointment_service = AppointmentService(db)
        try:
            updated = await appointment_service.update_appointment(
                args.appointment_id,
                AppointmentUpdate(
                    appointment_date=target_date,
                    appointment_time=args.new_time,
                    status="RESCHEDULED"
                )
            )
            return {
                "status": "rescheduled",
                "appointment_id": updated.id,
                "booking_reference": updated.booking_reference,
                "doctor_name": updated.doctor.name if updated.doctor else "",
                "new_date": str(updated.appointment_date),
                "new_time": updated.appointment_time,
            }
        except HTTPException as he:
            return {"status": "conflict" if he.status_code == 409 else "error", "message": he.detail}
        except Exception as e:
            return {"status": "error", "message": f"Rescheduling failed: {str(e)}"}

    async def cancel_appointment(self, db: AsyncSession, args: CancelAppointmentInput) -> Dict[str, Any]:
        """Tool 7: Cancel an appointment with explicit confirmation check."""
        if not args.confirmation:
            return {
                "status": "confirmation_required",
                "appointment_id": args.appointment_id,
                "message": "Cancellation was not confirmed by the caller. Please explicitly confirm before cancelling."
            }

        appointment_service = AppointmentService(db)
        try:
            result = await appointment_service.delete_appointment(args.appointment_id)
            return {
                "status": "cancelled",
                "appointment_id": args.appointment_id,
                "message": result.get("message", "Appointment successfully cancelled.")
            }
        except HTTPException as he:
            return {"status": "not_found" if he.status_code == 404 else "error", "message": he.detail}

    async def get_hospital_information(self, db: AsyncSession, args: GetHospitalInformationInput) -> Dict[str, Any]:
        """Tool 8: Retrieve verified hospital information."""
        hospital_repo = HospitalRepository(db)
        hospital = await hospital_repo.get_primary_hospital()
        hospital_name = hospital.name if hospital else settings.HOSPITAL_NAME
        contact_number = hospital.contact_number if hospital else settings.HOSPITAL_PHONE
        address = hospital.address if hospital else settings.HOSPITAL_ADDRESS

        q_lower = args.query.lower()
        if "visit" in q_lower or "hour" in q_lower or "timing" in q_lower or "samay" in q_lower:
            answer = f"{hospital_name} visiting hours are: {settings.HOSPITAL_VISITING_HOURS}. Max 2 visitors allowed per patient."
        elif "emergency" in q_lower or "triage" in q_lower or "ambulance" in q_lower or "108" in q_lower:
            answer = f"{hospital_name} provides 24/7 emergency care at {address}. Emergency hotline is {settings.HOSPITAL_EMERGENCY_PHONE}."
        elif "insurance" in q_lower or "claim" in q_lower or "mediclaim" in q_lower or "tpa" in q_lower:
            answer = "We accept all major health insurance providers (Star Health, HDFC Ergo, ICICI Lombard, Care, etc.). Cashless TPA desk is located on the Ground Floor."
        elif "address" in q_lower or "location" in q_lower or "kahan" in q_lower or "pata" in q_lower:
            answer = f"{hospital_name} is located at {address}. Multi-level patient parking is available at Gate 2."
        else:
            answer = f"{hospital_name} is a multi-specialty hospital with Cardiology, Pediatrics, Orthopedics, Neurology, and Dermatology departments. For queries call {contact_number}."

        return {
            "status": "success",
            "query": args.query,
            "hospital_name": hospital_name,
            "info": answer
        }

    async def request_human_handoff(self, db: AsyncSession, args: RequestHumanHandoffInput) -> Dict[str, Any]:
        """Tool 9: Request seamless escalation to a human hospital receptionist."""
        logger.warning(f"Human handoff requested. Reason: {args.reason}")
        return {
            "status": "handoff_initiated",
            "reason": args.reason,
            "transfer_number": settings.HOSPITAL_PHONE,
            "message": "Call is being transferred to a human hospital staff member. Please stay on the line."
        }

    # =====================================================================
    # Unified Safe Dispatcher
    # =====================================================================

    async def execute(self, tool_name: str, arguments: Dict[str, Any], db: AsyncSession) -> Dict[str, Any]:
        """
        Validate tool arguments using Pydantic and safely execute against service layer.
        """
        logger.info(f"Executing tool '{tool_name}' with arguments {arguments}")
        try:
            if tool_name == "search_doctors":
                validated = SearchDoctorsInput(**arguments)
                return await self.search_doctors(db, validated)
            elif tool_name == "get_doctor_details":
                validated = GetDoctorDetailsInput(**arguments)
                return await self.get_doctor_details(db, validated)
            elif tool_name == "check_availability":
                validated = CheckAvailabilityInput(**arguments)
                return await self.check_availability(db, validated)
            elif tool_name == "register_patient":
                validated = RegisterPatientInput(**arguments)
                return await self.register_patient(db, validated)
            elif tool_name == "book_appointment":
                validated = BookAppointmentInput(**arguments)
                return await self.book_appointment(db, validated)
            elif tool_name == "reschedule_appointment":
                validated = RescheduleAppointmentInput(**arguments)
                return await self.reschedule_appointment(db, validated)
            elif tool_name == "cancel_appointment":
                validated = CancelAppointmentInput(**arguments)
                return await self.cancel_appointment(db, validated)
            elif tool_name == "get_hospital_information":
                validated = GetHospitalInformationInput(**arguments)
                return await self.get_hospital_information(db, validated)
            elif tool_name == "request_human_handoff":
                validated = RequestHumanHandoffInput(**arguments)
                return await self.request_human_handoff(db, validated)
            else:
                return {"status": "error", "message": f"Unknown tool: '{tool_name}'"}
        except ValueError as ve:
            return {"status": "validation_error", "message": str(ve)}
        except Exception as e:
            logger.error(f"Unexpected error executing tool '{tool_name}': {e}", exc_info=True)
            return {"status": "error", "message": f"Tool execution failed: {str(e)}"}

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """
        Return the 9 tools in standard OpenAI/Gemini function-calling JSON format.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_doctors",
                    "description": "Search active doctors in the hospital by clinical department or specialization (e.g. Cardiology, Dermatology, Orthopedics, Pediatrics, Neurology, General Medicine).",
                    "parameters": SearchDoctorsInput.model_json_schema(),
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_doctor_details",
                    "description": "Get detailed information about a doctor by their unique doctor ID.",
                    "parameters": GetDoctorDetailsInput.model_json_schema(),
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "check_availability",
                    "description": "Check available appointment time slots for a specific doctor on a given date (YYYY-MM-DD).",
                    "parameters": CheckAvailabilityInput.model_json_schema(),
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "register_patient",
                    "description": "Register a new patient or look up existing patient by name and phone number.",
                    "parameters": RegisterPatientInput.model_json_schema(),
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "book_appointment",
                    "description": "Book a confirmed appointment in the database for a patient with a doctor at a chosen date and time slot.",
                    "parameters": BookAppointmentInput.model_json_schema(),
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "reschedule_appointment",
                    "description": "Reschedule an existing appointment to a new date and time slot.",
                    "parameters": RescheduleAppointmentInput.model_json_schema(),
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "cancel_appointment",
                    "description": "Cancel an existing appointment in the hospital database with explicit confirmation.",
                    "parameters": CancelAppointmentInput.model_json_schema(),
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_hospital_information",
                    "description": "Retrieve verified information about hospital visiting hours, address, emergency department, parking, and insurance claims.",
                    "parameters": GetHospitalInformationInput.model_json_schema(),
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "request_human_handoff",
                    "description": "Escalate the caller to a human hospital receptionist or supervisor.",
                    "parameters": RequestHumanHandoffInput.model_json_schema(),
                }
            },
        ]


# Singleton instance
tool_registry = SafeToolRegistry()
