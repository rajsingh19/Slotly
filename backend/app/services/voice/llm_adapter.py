import re
import json
import httpx
from typing import List, Dict, Any, Optional
from datetime import date, timedelta
from app.core.config import settings
from app.core.logging import get_logger
from app.services.voice.base import BaseLLMService

logger = get_logger(__name__)

HOSPITAL_SYSTEM_PROMPT = """You are Maya, the friendly, empathetic, and professional AI Voice Receptionist at Apex Multi-Specialty Hospital.
Your responsibilities:
1. Warmly greet callers and understand their medical or administrative needs.
2. Answer questions about hospital departments, doctor specialties, visiting hours, insurance, and emergency triage.
3. Check doctor availability and schedule appointments.
4. Assist with rescheduling or cancelling existing appointments.
5. In case of life-threatening emergencies (e.g., chest pain, stroke, severe bleeding), immediately advise the caller to dial 911 or visit our 24/7 Emergency Ward.
Always keep responses concise, conversational, and suitable for voice speech. Avoid long markdown lists or complex formatting.
"""

# Available tool definitions for function calling
RECEPTIONIST_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_doctor_availability",
            "description": "Check available appointment slots for doctors by specialty or doctor name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "specialty": {"type": "string", "description": "Medical specialty, e.g. Cardiology, Orthopedics, Pediatrics, Neurology, General Medicine"},
                    "doctor_name": {"type": "string", "description": "Doctor's name, e.g. Dr. Rajesh Sharma"},
                    "date": {"type": "string", "description": "Target date in YYYY-MM-DD format (defaults to today or tomorrow)"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book a new doctor consultation appointment for a patient.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {"type": "string", "description": "Full name of the patient"},
                    "patient_phone": {"type": "string", "description": "Contact phone number of the patient"},
                    "doctor_id": {"type": "integer", "description": "Doctor ID"},
                    "slot_id": {"type": "integer", "description": "Selected TimeSlot ID"},
                    "reason_for_visit": {"type": "string", "description": "Brief description of symptom or consultation reason"}
                },
                "required": ["patient_name", "patient_phone", "doctor_id", "slot_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_appointment",
            "description": "Reschedule an existing appointment to a new date/time slot.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_identifier": {"type": "string", "description": "Appointment Number (e.g. APT-20261105-XXXX) or Phone number"},
                    "new_slot_id": {"type": "integer", "description": "ID of the new time slot to move to"},
                    "reason": {"type": "string", "description": "Reason for rescheduling"}
                },
                "required": ["appointment_identifier", "new_slot_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel a previously booked appointment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_identifier": {"type": "string", "description": "Appointment Number or Phone number"},
                    "reason": {"type": "string", "description": "Reason for cancellation"}
                },
                "required": ["appointment_identifier"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_hospital_info",
            "description": "Retrieve information about hospital facilities, visiting hours, insurance, directions, emergency helpline.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Topic or query, e.g. visiting hours, insurance, parking, location, emergency"}
                },
                "required": ["query"]
            }
        }
    }
]


class MockHospitalLLMService(BaseLLMService):
    """
    Intelligent zero-cost dialogue and state manager for local development & testing.
    Understands caller intents, extracts parameters, and issues tool calls or replies.
    """
    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str = HOSPITAL_SYSTEM_PROMPT,
        available_tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        last_message = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_message = m.get("content", "").strip()
                break

        msg_lower = last_message.lower()

        # 1. Emergency Detection
        emergency_keywords = ["chest pain", "heart attack", "can't breathe", "cannot breathe", "severe bleeding", "unconscious", "stroke", "emergency"]
        if any(k in msg_lower for k in emergency_keywords):
            return {
                "content": f"This sounds like a medical emergency. Please dial {settings.HOSPITAL_EMERGENCY_PHONE} immediately or proceed directly to our 24/7 Emergency Department at {settings.HOSPITAL_ADDRESS}. An emergency physician is on standby.",
                "tool_calls": None,
                "finish_reason": "stop"
            }

        # 2. Reschedule Appointment Intent
        if "reschedule" in msg_lower or "change appointment" in msg_lower or "move appointment" in msg_lower:
            apt_match = re.search(r"APT-[\w-]+", last_message, re.IGNORECASE)
            apt_id = apt_match.group(0).upper() if apt_match else ""
            time_match = re.search(r"\b([01]?[0-9]|2[0-3]):[0-5][0-9]\b", last_message)
            req_time = time_match.group(0) if time_match else "11:00"
            target_date = (date.today() + timedelta(days=2)).isoformat()
            if "tomorrow" in msg_lower:
                target_date = (date.today() + timedelta(days=1)).isoformat()

            return {
                "content": f"Rescheduling your appointment {apt_id or 'on file'} to {target_date} at {req_time}.",
                "tool_calls": [
                    {
                        "id": "call_reschedule",
                        "function": {
                            "name": "reschedule_appointment",
                            "arguments": json.dumps({
                                "appointment_identifier": apt_id,
                                "new_date": target_date,
                                "new_time": req_time
                            })
                        }
                    }
                ],
                "finish_reason": "tool_calls"
            }

        # 3. Cancel Appointment Intent
        if "cancel" in msg_lower and ("appointment" in msg_lower or "booking" in msg_lower or "visit" in msg_lower):
            apt_match = re.search(r"APT-[\w-]+", last_message, re.IGNORECASE)
            apt_id = apt_match.group(0).upper() if apt_match else ""
            return {
                "content": f"I am cancelling appointment {apt_id or 'on file'} for you right away.",
                "tool_calls": [
                    {
                        "id": "call_cancel",
                        "function": {
                            "name": "cancel_appointment",
                            "arguments": json.dumps({"appointment_identifier": apt_id, "reason": "Patient requested via voice assistant"})
                        }
                    }
                ],
                "finish_reason": "tool_calls"
            }

        # 4. Book Appointment Intent (Explicit booking or confirmation of proposed slot)
        if ("book" in msg_lower or "confirm" in msg_lower or "yes" in msg_lower or "please schedule" in msg_lower) and not ("cancel" in msg_lower or "reschedule" in msg_lower):
            time_match = re.search(r"\b([01]?[0-9]|2[0-3]):[0-5][0-9]\b", last_message)
            req_time = time_match.group(0) if time_match else "10:00"
            phone_match = re.search(r"(\+?[0-9]{10,15})", last_message)
            req_phone = phone_match.group(0) if phone_match else "+15557778888"
            pat_name = "Eleanor Vance" if "eleanor" in msg_lower else "Valued Patient"
            target_date = (date.today() + timedelta(days=1)).isoformat()

            return {
                "content": f"Booking appointment for {pat_name} at {req_time}.",
                "tool_calls": [
                    {
                        "id": "call_book",
                        "function": {
                            "name": "book_appointment",
                            "arguments": json.dumps({
                                "patient_name": pat_name,
                                "patient_phone": req_phone,
                                "date": target_date,
                                "time": req_time,
                                "reason_for_visit": "General Consultation"
                            })
                        }
                    }
                ],
                "finish_reason": "tool_calls"
            }

        # 5. Check Doctor Availability Intent
        spec_map = {
            "cardiologist": "Cardiology",
            "cardiology": "Cardiology",
            "orthopedic": "Orthopedics",
            "orthopedics": "Orthopedics",
            "pediatrician": "Pediatrics",
            "pediatrics": "Pediatrics",
            "neurologist": "Neurology",
            "neurology": "Neurology",
            "dermatologist": "Dermatology",
            "dermatology": "Dermatology",
            "general physician": "General Medicine",
            "general medicine": "General Medicine",
        }
        detected_spec = None
        for k, v in spec_map.items():
            if k in msg_lower:
                detected_spec = v
                break

        if "doctor" in msg_lower or "appointment" in msg_lower or "available" in msg_lower or detected_spec:
            # Check availability tool call
            spec_arg = detected_spec or "Cardiology"
            target_date = (date.today() + timedelta(days=1)).isoformat()
            if "tomorrow" in msg_lower:
                target_date = (date.today() + timedelta(days=1)).isoformat()

            return {
                "content": f"Let me check the available doctors and appointment slots in {spec_arg} for {target_date}.",
                "tool_calls": [
                    {
                        "id": "call_check_avail",
                        "function": {
                            "name": "check_doctor_availability",
                            "arguments": json.dumps({"specialty": spec_arg, "date": target_date})
                        }
                    }
                ],
                "finish_reason": "tool_calls"
            }

        # 5. Hospital FAQs: visiting hours, address, insurance, parking
        if "visiting" in msg_lower or "hours" in msg_lower:
            return {
                "content": f"Visiting hours at {settings.HOSPITAL_NAME} are: {settings.HOSPITAL_VISITING_HOURS}. Only two visitors are allowed per patient at a time.",
                "tool_calls": None,
                "finish_reason": "stop"
            }

        if "insurance" in msg_lower or "mediclaim" in msg_lower:
            return {
                "content": "We accept all major health insurance providers, including BlueCross, Medicare, Cigna, UnitedHealthcare, and Aetna. Cashless TPA claims desk is on the ground floor.",
                "tool_calls": None,
                "finish_reason": "stop"
            }

        if "address" in msg_lower or "location" in msg_lower or "where" in msg_lower:
            return {
                "content": f"{settings.HOSPITAL_NAME} is located at {settings.HOSPITAL_ADDRESS}. Free multi-level patient parking is available at Gate 2.",
                "tool_calls": None,
                "finish_reason": "stop"
            }

        # 6. Default Welcome Greeting
        return {
            "content": f"Hello! Welcome to {settings.HOSPITAL_NAME}. I am Maya, your AI receptionist. How may I assist you today? You can ask about doctor availability, book or reschedule an appointment, or check visiting hours.",
            "tool_calls": None,
            "finish_reason": "stop"
        }


class GeminiLLMService(BaseLLMService):
    """
    Google Gemini API dialogue integration.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = settings.LLM_MODEL or "gemini-1.5-flash"

    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str = HOSPITAL_SYSTEM_PROMPT,
        available_tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        if not self.api_key:
            return await MockHospitalLLMService().generate_response(messages, system_prompt, available_tools)

        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        
        # Convert messages to Gemini contents format
        contents = []
        for m in messages:
            role = "user" if m.get("role") in ("user", "system") else "model"
            contents.append({
                "role": role,
                "parts": [{"text": m.get("content", "")}]
            })

        payload: Dict[str, Any] = {
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {
                "temperature": settings.LLM_TEMPERATURE,
                "maxOutputTokens": 300,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(endpoint, json=payload)
                res.raise_for_status()
                data = res.json()
                candidates = data.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    text_parts = [p.get("text", "") for p in parts if "text" in p]
                    reply_text = " ".join(text_parts).strip()
                    return {
                        "content": reply_text or "How can I help you with your hospital appointment today?",
                        "tool_calls": None,
                        "finish_reason": "stop"
                    }
        except Exception as e:
            logger.error(f"Gemini API error: {e}. Falling back to rule engine.", exc_info=True)
            return await MockHospitalLLMService().generate_response(messages, system_prompt, available_tools)

        return await MockHospitalLLMService().generate_response(messages, system_prompt, available_tools)


class OpenAILLMService(BaseLLMService):
    """
    OpenAI / Groq compatible chat completions service.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = settings.LLM_MODEL or "gpt-4o-mini"

    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        system_prompt: str = HOSPITAL_SYSTEM_PROMPT,
        available_tools: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        if not self.api_key:
            return await MockHospitalLLMService().generate_response(messages, system_prompt, available_tools)

        endpoint = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        full_messages = [{"role": "system", "content": system_prompt}] + messages
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": full_messages,
            "temperature": settings.LLM_TEMPERATURE,
        }
        if available_tools:
            payload["tools"] = available_tools

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(endpoint, headers=headers, json=payload)
                res.raise_for_status()
                data = res.json()
                choice = data["choices"][0]
                message = choice["message"]
                return {
                    "content": message.get("content") or "",
                    "tool_calls": message.get("tool_calls"),
                    "finish_reason": choice.get("finish_reason", "stop")
                }
        except Exception as e:
            logger.error(f"OpenAI API error: {e}. Falling back to rule engine.", exc_info=True)
            return await MockHospitalLLMService().generate_response(messages, system_prompt, available_tools)


def get_llm_service() -> BaseLLMService:
    provider = settings.LLM_PROVIDER.lower()
    if provider == "gemini" and settings.GEMINI_API_KEY:
        return GeminiLLMService()
    elif provider == "openai" and settings.OPENAI_API_KEY:
        return OpenAILLMService()
    return MockHospitalLLMService()
