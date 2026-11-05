import re
import time
from enum import Enum
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from zoneinfo import ZoneInfo

from app.core.config import settings
from app.core.logging import get_logger
from app.services.voice.agent.tools import SPECIALTY_NORMALIZATION_MAP

logger = get_logger(__name__)


class ConversationState(str, Enum):
    GREETING = "GREETING"
    IDENTIFY_INTENT = "IDENTIFY_INTENT"
    SELECT_SPECIALIZATION = "SELECT_SPECIALIZATION"
    SELECT_DOCTOR = "SELECT_DOCTOR"
    SELECT_DATE = "SELECT_DATE"
    CHECK_SLOTS = "CHECK_SLOTS"
    SELECT_TIME = "SELECT_TIME"
    COLLECT_PATIENT_DETAILS = "COLLECT_PATIENT_DETAILS"
    CONFIRM_BOOKING = "CONFIRM_BOOKING"
    BOOK_APPOINTMENT = "BOOK_APPOINTMENT"
    BOOKING_SUCCESS = "BOOKING_SUCCESS"
    END_CONVERSATION = "END_CONVERSATION"
    EMERGENCY_TRIAGE = "EMERGENCY_TRIAGE"
    HUMAN_HANDOFF = "HUMAN_HANDOFF"
    RESCHEDULE_FLOW = "RESCHEDULE_FLOW"
    CANCEL_FLOW = "CANCEL_FLOW"


def get_current_date_in_hospital_tz() -> date:
    """Get current date in configured hospital timezone (defaults to Asia/Kolkata)."""
    try:
        tz = ZoneInfo(settings.TIMEZONE)
        return datetime.now(tz).date()
    except Exception:
        return date.today()


class ConversationContext:
    """
    Stateful conversational memory tracking all collected entities,
    dialogue turns, and deterministic state transitions per call.
    """

    def __init__(self, session_id: str, caller_phone: Optional[str] = None):
        self.session_id: str = session_id
        self.caller_phone: str = caller_phone or "+15551234567"
        self.current_state: ConversationState = ConversationState.GREETING
        self.language: str = "hinglish"  # "hi", "en", "hinglish"
        
        # Booking entities
        self.specialization: Optional[str] = None
        self.doctor_id: Optional[int] = None
        self.doctor_name: Optional[str] = None
        self.appointment_date: Optional[date] = None
        self.appointment_time: Optional[str] = None
        self.patient_id: Optional[int] = None
        self.patient_name: Optional[str] = None
        self.patient_phone: Optional[str] = self.caller_phone
        self.booking_reference: Optional[str] = None
        self.appointment_id: Optional[int] = None
        
        # Intermediate state data
        self.available_slots: List[str] = []
        self.idempotency_key: Optional[str] = None
        self.history: List[Dict[str, str]] = []
        self.retry_count: int = 0
        self.handoff_reason: Optional[str] = None
        self.emergency_detected: bool = False
        self.start_time: float = time.time()
        self.call_session_db_id: Optional[int] = None

    def is_expired(self) -> bool:
        """Check if call duration has exceeded max allowed duration."""
        return (time.time() - self.start_time) > settings.MAX_CALL_DURATION_SECONDS


class DeterministicNLP:
    """
    Robust rule-based Indian conversational NLP parser supporting
    Hindi, English, and Hinglish for zero-latency, deterministic extraction.
    """

    EMERGENCY_PATTERNS = [
        r"\b(chest pain|heart attack|stroke|severe bleeding|heavy bleeding)\b",
        r"\b(seene mein dard|chhati mein dard|dil ka daura|saans nahi aa rahi|saans phool)\b",
        r"\b(cannot breathe|can't breathe|unconscious|behosh|khoon beh raha)\b",
        r"\b(emergency|turant doctor|icu|urgent ambulance)\b",
    ]

    HANDOFF_PATTERNS = [
        r"\b(human|person|agent|receptionist|staff|representative|executive)\b",
        r"\b(insaan se baat|kisi se baat|asli insaan|call transfer|transfer call)\b",
        r"\b(customer care|supervisor|manager se baat)\b",
    ]

    MEDICAL_ADVICE_PATTERNS = [
        r"\b(kaunsi dawai|medicine|prescription|dawa|tablet|syrup|dosage)\b",
        r"\b(kya khana chahiye|dawai batao|medicines for|cure|treatment for)\b",
    ]

    CONFIRMATION_PATTERNS = [
        r"\b(haan|ha|yes|sure|bilkul|theek hai|thik hai|confirm|kar do|kardo|kar dijiye|done|yep|yeah|okay|ok)\b"
    ]

    REJECTION_PATTERNS = [
        r"\b(nahi|na|no|cancel|mat karo|rehne do|wait|ruko|change|dont|don't)\b"
    ]

    @classmethod
    def detect_language(cls, text: str) -> str:
        """
        Detect whether utterance is Devanagari Hindi ('hi'), pure English ('en'),
        or Romanized Hindi / Hinglish ('hinglish'). Returns 'neutral' for numbers or short ambiguous words.
        """
        # If utterance contains Devanagari script characters
        if re.search(r"[\u0900-\u097F]", text):
            return "hi"

        t = text.lower()
        hindi_markers = [
            "mujhe", "hai", "chahiye", "karna", "dikhao", "batao", "baje", "subah",
            "shaam", "kaunsa", "kal", "parson", "aaj", "kripya", "dhanyawad",
            "namaste", "pranam", "karein", "mera", "meri", "aap", "aapko", "seene",
            "dard", "saans", "kisi", "insaan", "baat", "dil", "milna", "theek", "kardo"
        ]
        hindi_count = sum(1 for w in hindi_markers if w in t)

        english_markers = [
            "appointment", "doctor", "available", "schedule", "please", "tomorrow",
            "today", "yesterday", "hospital", "cardiology", "dermatology", "pediatrics",
            "chest", "pain", "father", "bleeding", "emergency", "human", "person",
            "cancel", "reschedule", "need", "with", "want"
        ]
        english_count = sum(1 for w in english_markers if w in t)

        if hindi_count > 0:
            return "hinglish"
        elif english_count > 0:
            return "en"
        return "neutral"

    @classmethod
    def is_emergency(cls, text: str) -> bool:
        t = text.lower()
        for pat in cls.EMERGENCY_PATTERNS:
            if re.search(pat, t, re.IGNORECASE):
                return True
        return False

    @classmethod
    def is_handoff_requested(cls, text: str) -> bool:
        t = text.lower()
        for pat in cls.HANDOFF_PATTERNS:
            if re.search(pat, t, re.IGNORECASE):
                return True
        return False

    @classmethod
    def is_medical_advice_requested(cls, text: str) -> bool:
        t = text.lower()
        for pat in cls.MEDICAL_ADVICE_PATTERNS:
            if re.search(pat, t, re.IGNORECASE):
                return True
        return False

    @classmethod
    def is_confirmed(cls, text: str) -> bool:
        t = text.lower()
        return any(re.search(pat, t, re.IGNORECASE) for pat in cls.CONFIRMATION_PATTERNS) and not any(re.search(pat, t, re.IGNORECASE) for pat in cls.REJECTION_PATTERNS)

    @classmethod
    def is_rejected(cls, text: str) -> bool:
        t = text.lower()
        return any(re.search(pat, t, re.IGNORECASE) for pat in cls.REJECTION_PATTERNS)

    @classmethod
    def extract_specialization(cls, text: str) -> Optional[str]:
        t = text.lower()
        for key, spec in SPECIALTY_NORMALIZATION_MAP.items():
            if re.search(r"\b" + re.escape(key) + r"\b", t):
                return spec
        return None

    @classmethod
    def extract_date(cls, text: str) -> Optional[date]:
        """Extract Indian relative dates or ISO dates."""
        t = text.lower()
        today = get_current_date_in_hospital_tz()

        if re.search(r"\b(parson|parso|day after tomorrow)\b", t):
            return today + timedelta(days=2)
        if re.search(r"\b(kal|tomorrow|agla din)\b", t):
            return today + timedelta(days=1)
        if re.search(r"\b(aaj|today|current day)\b", t):
            return today

        # Explicit YYYY-MM-DD
        iso_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", t)
        if iso_match:
            try:
                parsed = date.fromisoformat(iso_match.group(1))
                if parsed >= today:
                    return parsed
            except Exception:
                pass

        # Weekdays e.g. "Monday", "somwar", "Tuesday", "mangalwar"
        weekdays = {
            "somwar": 0, "monday": 0,
            "mangalwar": 1, "tuesday": 1,
            "budhwar": 2, "wednesday": 2,
            "guruwar": 3, "thursday": 3, "brihaspatiwar": 3,
            "shukrawar": 4, "friday": 4,
            "shaniwar": 5, "saturday": 5,
            "ravivar": 6, "sunday": 6, "itwar": 6,
        }
        for day_name, day_idx in weekdays.items():
            if day_name in t:
                days_ahead = (day_idx - today.weekday() + 7) % 7
                if days_ahead == 0:
                    days_ahead = 7  # Next week
                return today + timedelta(days=days_ahead)

        return None

    @classmethod
    def extract_time_slot(cls, text: str, available_slots: Optional[List[str]] = None) -> Optional[str]:
        """Extract appointment time slot like 10:00, 11 AM, 2 PM, 11 baje, 2 baje."""
        t = text.lower()
        
        # 1. Direct standard 24-hr format (e.g., 10:00, 14:30)
        direct_match = re.search(r"\b([01]?[0-9]|2[0-3]):[0-5][0-9]\b", t)
        if direct_match:
            val = direct_match.group(0)
            if len(val) == 4 and val[1] == ":":
                val = "0" + val
            return val

        # 2. 12-hour AM/PM (e.g. 11 am, 2 pm, 11:30 am)
        ampm_match = re.search(r"\b(1[0-2]|0?[1-9])(?::([0-5][0-9]))?\s*(am|pm)\b", t)
        if ampm_match:
            hr = int(ampm_match.group(1))
            mn = ampm_match.group(2) or "00"
            period = ampm_match.group(3).lower()
            if period == "pm" and hr < 12:
                hr += 12
            elif period == "am" and hr == 12:
                hr = 0
            return f"{hr:02d}:{mn}"

        # 3. Hindi 'baje' e.g. "11 baje", "2 baje", "10 baje"
        baje_match = re.search(r"\b(1[0-2]|0?[1-9])(?:\s*(?:aur|and|saadhe|baje))?\s*baje\b", t)
        if baje_match:
            hr = int(baje_match.group(1))
            # Afternoon heuristic: 1, 2, 3, 4, 5 baje is usually PM in hospital outpatient
            if "dopahar" in t or "shaam" in t or hr in [1, 2, 3, 4, 5]:
                if hr < 12:
                    hr += 12
            return f"{hr:02d}:00"

        # 4. If caller says "first slot", "pehla", "morning", "subah", pick from available
        if available_slots:
            if "first" in t or "pehla" in t or "subah" in t or "earliest" in t:
                return available_slots[0]
            if "second" in t or "dusra" in t and len(available_slots) > 1:
                return available_slots[1]
            if "last" in t or "aakhri" in t or "shaam" in t:
                return available_slots[-1]

        return None

    @classmethod
    def extract_patient_details(cls, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Extract patient full name and 10-digit phone number."""
        t = text.strip()
        
        # Phone: 10 to 15 digits
        phone_match = re.search(r"(\+?[0-9]{10,15})", t)
        phone = phone_match.group(1) if phone_match else None

        # Name: e.g. "naam Rahul Verma hai" or "Mera naam Priya Sharma" or "Rahul Verma"
        name = None
        name_patterns = [
            r"(?:naam|name\s+is|patient\s+is|patient\s+name\s+is)\s+([A-Za-z\s]+?)(?:\s+hai|\s+phone|\s+number|\s*[,.]|$)",
            r"(?:mera\s+naam|patient\s+naam)\s+([A-Za-z\s]+?)(?:\s+hai|\s+aur|\s*[,.]|$)",
            r"(?:for|booking\s+for|appointment\s+for)\s+([A-Za-z\s]+?)(?:\s+at|\s+on|\s+phone|\s+number|\s*[,.]|$)",
        ]
        for pat in name_patterns:
            m = re.search(pat, t, re.IGNORECASE)
            if m:
                cand = m.group(1).strip()
                if len(cand.split()) >= 1 and cand.lower() not in ["doctor", "appointment", "apex"]:
                    name = cand.title()
                    break

        if not name and not phone:
            # Fallback: check if text looks like a bare name with at least 2 words (e.g. "Rahul Verma" or "Eleanor Vance")
            words = t.split()
            ignored = [
                "haan", "nahi", "theek", "kal", "parson", "aaj", "yes", "no", "cancel", "confirm",
                "today", "tomorrow", "yesterday", "morning", "evening", "afternoon", "night",
                "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
                "somwar", "mangalwar", "budhwar", "guruwar", "shukrawar", "shaniwar", "ravivar",
                "doctor", "appointment", "hospital", "clinic", "help", "need", "book", "slot", "slots"
            ]
            if 2 <= len(words) <= 4 and all(w.isalpha() for w in words):
                if not any(w.lower() in ignored for w in words):
                    name = t.title()

        return name, phone

    @classmethod
    def extract_booking_reference(cls, text: str) -> Optional[str]:
        """Extract booking reference starting with APT-."""
        match = re.search(r"\b(APT-[\w-]+)\b", text, re.IGNORECASE)
        return match.group(1).upper() if match else None
