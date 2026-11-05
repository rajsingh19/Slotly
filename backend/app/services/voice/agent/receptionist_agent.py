import re
import json
import uuid
import time
from datetime import date, datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.services.voice.agent.state_machine import (
    ConversationState,
    ConversationContext,
    DeterministicNLP,
    get_current_date_in_hospital_tz
)
from app.services.voice.agent.tools import (
    tool_registry,
    SearchDoctorsInput,
    GetDoctorDetailsInput,
    CheckAvailabilityInput,
    RegisterPatientInput,
    BookAppointmentInput,
    RescheduleAppointmentInput,
    CancelAppointmentInput,
    GetHospitalInformationInput,
    RequestHumanHandoffInput
)
from app.services.voice.agent.prompts import AI_RECEPTIONIST_SYSTEM_PROMPT

logger = get_logger(__name__)


class HospitalReceptionistAgent:
    """
    Intelligent Conversational AI Hospital Receptionist Agent (Maya).
    Features:
    - Multilingual natural dialogue (Hindi, English, Hinglish).
    - Deterministic state machine with safe transitions.
    - Zero hallucination: all availability & bookings come from PostgreSQL/SQLite database.
    - Medical safety filters & immediate emergency triage.
    - Strict one-question-at-a-time conversation discipline.
    """

    def __init__(self):
        self.tools = tool_registry

    async def handle_turn(
        self,
        db: AsyncSession,
        context: ConversationContext,
        user_text: str
    ) -> Tuple[str, Optional[str], Optional[Dict[str, Any]]]:
        """
        Process a single spoken user utterance:
        Returns:
            (spoken_response, action_type, action_payload)
        """
        t_cleaned = user_text.strip()
        context.history.append({"role": "user", "content": t_cleaned})

        # Update language detection
        detected_lang = DeterministicNLP.detect_language(t_cleaned)
        if detected_lang != "neutral":
            context.language = detected_lang

        lang = context.language

        # -----------------------------------------------------------------
        # 1. Critical Safety Filter: Emergency Triage
        # -----------------------------------------------------------------
        if DeterministicNLP.is_emergency(t_cleaned):
            context.current_state = ConversationState.EMERGENCY_TRIAGE
            context.emergency_detected = True
            logger.warning(f"EMERGENCY DETECTED in session {context.session_id}: '{t_cleaned}'")
            
            if lang == "hi":
                reply = f"यह एक मेडिकल इमरजेंसी लग रही है! कृपया तुरंत {settings.HOSPITAL_EMERGENCY_PHONE} पर कॉल करें या सीधे हमारे 24/7 इमरजेंसी वार्ड में पहुँचें। डॉक्टर्स स्टैंडबाय पर हैं।"
            elif lang == "en":
                reply = f"This sounds like a medical emergency! Please dial {settings.HOSPITAL_EMERGENCY_PHONE} immediately or proceed directly to our 24/7 Emergency Department at {settings.HOSPITAL_ADDRESS}."
            else:
                reply = f"Yeh ek medical emergency lag rahi hai! Please turant {settings.HOSPITAL_EMERGENCY_PHONE} par dial karein ya hamare 24/7 Emergency Ward me pahuchein. Hamari emergency team ready hai."
            
            context.history.append({"role": "assistant", "content": reply})
            return reply, "EMERGENCY_ALERT", {"emergency": True, "hotline": settings.HOSPITAL_EMERGENCY_PHONE}

        # -----------------------------------------------------------------
        # 2. Critical Safety Filter: Medical Prescription / Diagnosis Prohibition
        # -----------------------------------------------------------------
        if DeterministicNLP.is_medical_advice_requested(t_cleaned):
            if lang == "hi":
                reply = "एक AI रिसेप्शनिस्ट होने के नाते मैं कोई दवाई या मेडिकल डायग्नोसिस नहीं दे सकती। इसके लिए आपको डॉक्टर से कंसल्ट करना चाहिए। क्या मैं आपके लिए अपॉइंटमेंट बुक कर दूँ?"
            elif lang == "en":
                reply = "As an AI hospital receptionist, I cannot prescribe medicines or provide medical diagnosis. Please consult one of our qualified doctors. Would you like me to book an appointment for you?"
            else:
                reply = "Main ek AI receptionist hoon, isliye koi dawai ya diagnosis suggest nahi kar sakti. Proper checkup ke liye aapko doctor se milna chahiye. Kya main appointment schedule kar doon?"

            context.history.append({"role": "assistant", "content": reply})
            return reply, "ADVICE_RESTRICTION", {}

        # -----------------------------------------------------------------
        # 3. Human Handoff Request
        # -----------------------------------------------------------------
        if DeterministicNLP.is_handoff_requested(t_cleaned):
            context.current_state = ConversationState.HUMAN_HANDOFF
            context.handoff_reason = t_cleaned
            handoff_res = await self.tools.request_human_handoff(
                db, RequestHumanHandoffInput(reason=f"Caller requested human transfer: '{t_cleaned}'")
            )
            if lang == "hi":
                reply = f"मैं आपकी कॉल तुरंत हमारे हॉस्पिटल स्टाफ रिसेप्शनिस्ट को ट्रांसफर कर रही हूँ। कृपया लाइन पर बने रहें।"
            elif lang == "en":
                reply = f"I am transferring your call to our hospital reception staff right away. Please hold the line."
            else:
                reply = f"Main aapki call hamare hospital staff receptionist ko transfer kar rahi hoon. Please line par bane rahein."

            context.history.append({"role": "assistant", "content": reply})
            return reply, "HUMAN_HANDOFF", handoff_res

        # -----------------------------------------------------------------
        # 4. Hospital FAQ / Information Intent
        # -----------------------------------------------------------------
        info_keywords = ["visiting", "hours", "timing", "samay", "kahan", "where", "address", "location", "pata", "insurance", "mediclaim", "tpa", "parking"]
        if any(w in t_cleaned.lower() for w in info_keywords) and not any(w in t_cleaned.lower() for w in ["appointment", "book", "doctor", "cancel", "reschedule"]):
            info_res = await self.tools.get_hospital_information(db, GetHospitalInformationInput(query=t_cleaned))
            reply = info_res.get("info", f"{settings.HOSPITAL_NAME} visiting hours are: {settings.HOSPITAL_VISITING_HOURS}.")
            context.history.append({"role": "assistant", "content": reply})
            return reply, "HOSPITAL_INFO", info_res

        # -----------------------------------------------------------------
        # 5. Cancellation Flow
        # -----------------------------------------------------------------
        if "cancel" in t_cleaned.lower() and context.current_state != ConversationState.CONFIRM_BOOKING:
            context.current_state = ConversationState.CANCEL_FLOW
            ref_in_msg = DeterministicNLP.extract_booking_reference(t_cleaned)
            if ref_in_msg:
                context.booking_reference = ref_in_msg

            if not context.booking_reference:
                if lang == "hi":
                    reply = "अपॉइंटमेंट कैंसिल करने के लिए कृपया अपना बुकिंग रेफरेंस नंबर (जैसे APT-XXXX) या रजिस्टर्ड फोन नंबर बताएं।"
                elif lang == "en":
                    reply = "To cancel your appointment, please provide your booking reference number (e.g. APT-XXXX) or registered phone number."
                else:
                    reply = "Appointment cancel karne ke liye please apna booking reference number (jaise APT-...) ya registered phone number batayein."
                context.history.append({"role": "assistant", "content": reply})
                return reply, "AWAIT_CANCEL_IDENTIFIER", {}

            # If user confirms or explicitly requests cancellation
            if (
                DeterministicNLP.is_confirmed(t_cleaned)
                or "cancel kar do" in t_cleaned.lower()
                or "cancel it" in t_cleaned.lower()
                or "please cancel" in t_cleaned.lower()
                or "kripya cancel" in t_cleaned.lower()
            ):
                from app.services.appointment_service import AppointmentService
                apt_service = AppointmentService(db)
                apt = await apt_service.find_appointment_by_ref_or_phone(context.booking_reference)
                if not apt:
                    reply = f"Could not find an active appointment with reference {context.booking_reference}."
                    return reply, "CANCEL_FAILED", {}

                cancel_res = await self.tools.cancel_appointment(
                    db, CancelAppointmentInput(appointment_id=apt.id, confirmation=True)
                )
                if lang == "hi":
                    reply = f"आपकी अपॉइंटमेंट {context.booking_reference} सफलतापूर्वक कैंसिल कर दी गई है।"
                elif lang == "en":
                    reply = f"Your appointment {context.booking_reference} has been successfully cancelled."
                else:
                    reply = f"Aapki appointment {context.booking_reference} cancel ho chuki hai. Kya aap koi doosra slot book karna chahte hain?"

                context.current_state = ConversationState.END_CONVERSATION
                context.history.append({"role": "assistant", "content": reply})
                return reply, "APPOINTMENT_CANCELLED", cancel_res
            else:
                # Ask explicit confirmation before cancelling
                if lang == "hi":
                    reply = f"क्या आप वाकई अपॉइंटमेंट {context.booking_reference} को कैंसिल करना चाहते हैं? कृपया 'हाँ' या 'ना' में पुष्टि करें।"
                elif lang == "en":
                    reply = f"Are you sure you want to cancel appointment {context.booking_reference}? Please confirm with 'yes' or 'no'."
                else:
                    reply = f"Kya aap confirm appointment {context.booking_reference} cancel karna chahte hain? Please haan ya na me batayein."
                context.history.append({"role": "assistant", "content": reply})
                return reply, "CONFIRM_CANCEL", {"booking_reference": context.booking_reference}

        # -----------------------------------------------------------------
        # 6. Rescheduling Flow
        # -----------------------------------------------------------------
        if ("reschedule" in t_cleaned.lower() or "change appointment" in t_cleaned.lower() or "move appointment" in t_cleaned.lower()) and context.current_state != ConversationState.CONFIRM_BOOKING:
            context.current_state = ConversationState.RESCHEDULE_FLOW
            ref_in_msg = DeterministicNLP.extract_booking_reference(t_cleaned)
            if ref_in_msg:
                context.booking_reference = ref_in_msg

            extracted_date = DeterministicNLP.extract_date(t_cleaned)
            extracted_time = DeterministicNLP.extract_time_slot(t_cleaned)
            if extracted_date:
                context.appointment_date = extracted_date
            if extracted_time:
                context.appointment_time = extracted_time

            if not context.booking_reference:
                if lang == "hi":
                    reply = "अपॉइंटमेंट रीशेड्यूल करने के लिए अपना बुकिंग रेफरेंस नंबर या रजिस्टर्ड फोन नंबर बताएं।"
                elif lang == "en":
                    reply = "Please share your booking reference number or phone number so I can reschedule your visit."
                else:
                    reply = "Appointment reschedule karne ke liye please apna booking reference number batayein."
                context.history.append({"role": "assistant", "content": reply})
                return reply, "AWAIT_RESCHEDULE_REF", {}

            if not context.appointment_date or not context.appointment_time:
                if lang == "hi":
                    reply = f"अपॉइंटमेंट {context.booking_reference} के लिए आपको किस नए दिन और समय पर आना है?"
                elif lang == "en":
                    reply = f"For appointment {context.booking_reference}, what new date and time would you prefer?"
                else:
                    reply = f"Appointment {context.booking_reference} ke liye aapko kis naye din aur time par aana hai?"
                context.history.append({"role": "assistant", "content": reply})
                return reply, "AWAIT_RESCHEDULE_SLOT", {}

            from app.services.appointment_service import AppointmentService
            apt = await AppointmentService(db).find_appointment_by_ref_or_phone(context.booking_reference)
            if not apt:
                reply = f"Could not find an active appointment with reference {context.booking_reference}."
                return reply, "RESCHEDULE_FAILED", {}

            resched_res = await self.tools.reschedule_appointment(
                db, RescheduleAppointmentInput(
                    appointment_id=apt.id,
                    new_date=context.appointment_date.isoformat(),
                    new_time=context.appointment_time
                )
            )
            if resched_res.get("status") == "rescheduled":
                if lang == "hi":
                    reply = f"आपकी अपॉइंटमेंट सफलतापूर्वक {context.appointment_date.isoformat()} को {context.appointment_time} पर रीशेड्यूल कर दी गई है।"
                elif lang == "en":
                    reply = f"Your appointment has been successfully rescheduled to {context.appointment_date.isoformat()} at {context.appointment_time}."
                else:
                    reply = f"Aapki appointment {resched_res.get('doctor_name', 'Doctor')} ke saath {context.appointment_date.isoformat()} ko {context.appointment_time} baje reschedule ho gayi hai."
                context.current_state = ConversationState.BOOKING_SUCCESS
                context.history.append({"role": "assistant", "content": reply})
                return reply, "APPOINTMENT_RESCHEDULED", resched_res
            else:
                reply = f"Rescheduling failed: {resched_res.get('message', 'Please choose another slot.')}"
                context.history.append({"role": "assistant", "content": reply})
                return reply, "RESCHEDULE_ERROR", resched_res

        # -----------------------------------------------------------------
        # 7. Main Appointment Booking State Workflow
        # -----------------------------------------------------------------
        # Check if caller named a doctor directly
        doctor_name_map = {
            "sharma": (1, "Dr. Rajesh Sharma", "Cardiology"),
            "rajesh": (1, "Dr. Rajesh Sharma", "Cardiology"),
            "menon": (2, "Dr. Priya Menon", "Pediatrics"),
            "priya": (2, "Dr. Priya Menon", "Pediatrics"),
            "malhotra": (3, "Dr. Vikram Malhotra", "Orthopedics"),
            "vikram": (3, "Dr. Vikram Malhotra", "Orthopedics"),
            "roy": (4, "Dr. Ananya Roy", "Neurology"),
            "ananya": (4, "Dr. Ananya Roy", "Neurology"),
            "patel": (5, "Dr. Sunita Patel", "Dermatology"),
            "sunita": (5, "Dr. Sunita Patel", "Dermatology"),
        }
        for doc_key, (doc_id, doc_n, doc_sp) in doctor_name_map.items():
            if doc_key in t_cleaned.lower():
                context.doctor_id = doc_id
                context.doctor_name = doc_n
                context.specialization = doc_sp
                logger.info(f"Direct doctor match: {doc_n} ({doc_sp})")
                break

        # Check if caller specified or changed specialization / symptom
        extracted_spec = DeterministicNLP.extract_specialization(t_cleaned)
        if extracted_spec and extracted_spec != context.specialization and not context.doctor_id:
            context.specialization = extracted_spec
            context.doctor_id = None
            context.doctor_name = None
            context.available_slots = []
            logger.info(f"Identified specialization: {context.specialization}")

        # Check if caller specified a date
        extracted_date = DeterministicNLP.extract_date(t_cleaned)
        if extracted_date:
            context.appointment_date = extracted_date
            logger.info(f"Identified target date: {context.appointment_date}")

        # Check if caller specified a time slot
        extracted_time = DeterministicNLP.extract_time_slot(t_cleaned, context.available_slots)
        if extracted_time:
            context.appointment_time = extracted_time
            logger.info(f"Identified time slot: {context.appointment_time}")

        # Check if caller provided patient details
        name_cand, phone_cand = DeterministicNLP.extract_patient_details(t_cleaned)
        if name_cand and not context.patient_name:
            context.patient_name = name_cand
        if phone_cand:
            context.patient_phone = phone_cand

        # --- Sub-State A: Need Specialization ---
        if not context.specialization and not context.doctor_id:
            context.current_state = ConversationState.SELECT_SPECIALIZATION
            if lang == "hi":
                reply = "नमस्ते! एपेक्स हॉस्पिटल में आपका स्वागत है। आप किस डिपार्टमेंट या डॉक्टर से कंसल्ट करना चाहते हैं?"
            elif lang == "en":
                reply = "Hello! Welcome to Apex Hospital. Which doctor or medical department would you like to consult with?"
            else:
                reply = "Hello! Apex Hospital me welcome. Aapko kis problem ya kis specialist doctor ko dikhana hai?"

            context.history.append({"role": "assistant", "content": reply})
            return reply, "AWAIT_SPECIALIZATION", {}

        # --- Sub-State B: Find Doctor for Specialization ---
        if context.specialization and not context.doctor_id:
            search_res = await self.tools.search_doctors(
                db, SearchDoctorsInput(specialization=context.specialization)
            )
            doctors = search_res.get("doctors", [])
            if not doctors:
                if lang == "hi":
                    reply = f"माफ़ कीजियेगा, वर्तमान में {context.specialization} में कोई एक्टिव डॉक्टर उपलब्ध नहीं हैं। क्या आप किसी अन्य विभाग में चेक करना चाहेंगे?"
                elif lang == "en":
                    reply = f"I am sorry, we currently do not have an active doctor in {context.specialization}. Would you like to check another department?"
                else:
                    reply = f"Sorry, {context.specialization} me abhi koi active doctor available nahi hain. Kisi aur department me check karein?"

                context.specialization = None
                context.history.append({"role": "assistant", "content": reply})
                return reply, "NO_DOCTORS_FOUND", {}

            # Assign first matching doctor
            chosen_doc = doctors[0]
            context.doctor_id = chosen_doc["id"]
            context.doctor_name = chosen_doc["name"]
            logger.info(f"Assigned doctor #{context.doctor_id} ({context.doctor_name}) for {context.specialization}")

        # --- Sub-State C: Need Date ---
        if not context.appointment_date:
            context.current_state = ConversationState.SELECT_DATE
            if lang == "hi":
                reply = f"बिल्कुल! आपको किस दिन अपॉइंटमेंट चाहिए? जैसे कि कल, परसों या कोई खास तारीख?"
            elif lang == "en":
                reply = f"Certainly! What day would you like the appointment with {context.doctor_name}? Today, tomorrow, or a specific date?"
            else:
                reply = f"Bilkul! Aapko kis din appointment chahiye? Kal, parson ya koi specific date?"

            context.history.append({"role": "assistant", "content": reply})
            return reply, "AWAIT_DATE", {"doctor_id": context.doctor_id, "doctor_name": context.doctor_name}

        # --- Sub-State D: Check Slots & Select Time ---
        if not context.appointment_time:
            context.current_state = ConversationState.CHECK_SLOTS
            avail_res = await self.tools.check_availability(
                db, CheckAvailabilityInput(
                    doctor_id=context.doctor_id,
                    date=context.appointment_date.isoformat()
                )
            )
            slots = avail_res.get("available_slots", [])
            context.available_slots = slots

            if not slots:
                if lang == "hi":
                    reply = f"{context.appointment_date.isoformat()} को {context.doctor_name} के सभी स्लॉट्स फुल हैं। क्या आप कोई अन्य दिन चुनना चाहेंगे?"
                elif lang == "en":
                    reply = f"All appointment slots for {context.doctor_name} are fully booked on {context.appointment_date.isoformat()}. Would you like to check another date?"
                else:
                    reply = f"{context.appointment_date.isoformat()} ko {context.doctor_name} ke sabhi slots fully booked hain. Kya aap doosre din ka check karna chahenge?"

                context.appointment_date = None
                context.history.append({"role": "assistant", "content": reply})
                return reply, "NO_SLOTS_AVAILABLE", avail_res

            # Slots found: prompt caller to pick a convenient slot
            context.current_state = ConversationState.SELECT_TIME
            
            # Format top 2-3 slots for spoken natural conversation
            slot_samples = []
            for s in slots[:3]:
                hr = int(s.split(":")[0])
                mn = s.split(":")[1]
                label = f"{hr if hr <= 12 else hr - 12}{':'+mn if mn != '00' else ''} {'AM' if hr < 12 else 'PM'}"
                slot_samples.append(label)

            slots_spoken = " aur ".join(slot_samples) if lang != "en" else " and ".join(slot_samples)
            day_label = "Kal" if context.appointment_date == get_current_date_in_hospital_tz() + timedelta(days=1) else str(context.appointment_date)

            if lang == "hi":
                reply = f"{day_label} {context.doctor_name} के {slots_spoken} स्लॉट्स उपलब्ध हैं। आपको कौनसा समय सुविधाजनक रहेगा?"
            elif lang == "en":
                reply = f"For {context.doctor_name} on {context.appointment_date.isoformat()}, available slots are {slots_spoken}. Which time suits you best?"
            else:
                reply = f"{day_label} {context.doctor_name} ke {slots_spoken} slots available hain. Aapko kaunsa convenient rahega?"

            context.history.append({"role": "assistant", "content": reply})
            return reply, "OFFER_SLOTS", {"slots": slots, "doctor_name": context.doctor_name}

        # --- Sub-State E: Collect Patient Details ---
        if not context.patient_name:
            context.current_state = ConversationState.COLLECT_PATIENT_DETAILS
            if lang == "hi":
                reply = "यह अपॉइंटमेंट किसके नाम पर बुक करनी है? कृपया अपना पूरा नाम और फ़ोन नंबर बताएं।"
            elif lang == "en":
                reply = "May I please have the patient's full name and contact phone number for this booking?"
            else:
                reply = "Yeh appointment kiske naam par book karni hai? Please apna full name aur phone number batayein."

            context.history.append({"role": "assistant", "content": reply})
            return reply, "AWAIT_PATIENT_DETAILS", {"time": context.appointment_time}

        # Ensure patient registered in DB
        if not context.patient_id:
            reg_res = await self.tools.register_patient(
                db, RegisterPatientInput(
                    name=context.patient_name,
                    phone_number=context.patient_phone or "+15551234567"
                )
            )
            if reg_res.get("status") == "success":
                context.patient_id = reg_res["patient_id"]
            else:
                reply = f"Patient registration issue: {reg_res.get('message', 'Please re-enter details')}"
                context.patient_name = None
                context.history.append({"role": "assistant", "content": reply})
                return reply, "PATIENT_DETAILS_ERROR", reg_res

        # --- Sub-State F: Confirmation & Booking Execution ---
        is_explicit_confirmation = DeterministicNLP.is_confirmed(t_cleaned) or "book" in t_cleaned.lower()
        if not is_explicit_confirmation and context.current_state != ConversationState.CONFIRM_BOOKING:
            context.current_state = ConversationState.CONFIRM_BOOKING
            day_label = "Kal" if context.appointment_date == get_current_date_in_hospital_tz() + timedelta(days=1) else str(context.appointment_date)
            
            if lang == "hi":
                reply = f"आपकी अपॉइंटमेंट {context.doctor_name} के साथ {day_label} को {context.appointment_time} पर {context.patient_name} के नाम से बुक की जा रही है। क्या मैं इसे कन्फर्म कर दूँ?"
            elif lang == "en":
                reply = f"I am ready to book your appointment with {context.doctor_name} on {context.appointment_date.isoformat()} at {context.appointment_time} for {context.patient_name}. Shall I confirm this?"
            else:
                reply = f"Aapki appointment {context.doctor_name} ke saath {day_label} ko {context.appointment_time} baje {context.patient_name} ke naam se book ki ja rahi hai. Kya main confirm kar doon?"

            context.history.append({"role": "assistant", "content": reply})
            return reply, "CONFIRM_BOOKING_PROMPT", {
                "doctor": context.doctor_name,
                "date": str(context.appointment_date),
                "time": context.appointment_time,
                "patient": context.patient_name
            }

        # --- Sub-State G: Execute Booking Upon Confirmation ---
        if is_explicit_confirmation or context.current_state == ConversationState.CONFIRM_BOOKING:
            if DeterministicNLP.is_confirmed(t_cleaned) or "book" in t_cleaned.lower():
                context.current_state = ConversationState.BOOK_APPOINTMENT
                # Generate idempotency key for this specific booking turn
                if not context.idempotency_key:
                    context.idempotency_key = f"book_{context.session_id}_{context.patient_id}_{context.doctor_id}_{context.appointment_date}_{context.appointment_time}"

                book_res = await self.tools.book_appointment(
                    db, BookAppointmentInput(
                        patient_id=context.patient_id,
                        doctor_id=context.doctor_id,
                        date=context.appointment_date.isoformat(),
                        time=context.appointment_time,
                        idempotency_key=context.idempotency_key
                    )
                )

                if book_res.get("status") == "booked":
                    context.current_state = ConversationState.BOOKING_SUCCESS
                    context.booking_reference = book_res["booking_reference"]
                    
                    if lang == "hi":
                        reply = f"बधाई हो! आपकी अपॉइंटमेंट बुक और कन्फर्म हो गई है। आपका बुकिंग रेफरेंस नंबर है {context.booking_reference}। क्या मैं आपकी किसी और चीज़ में मदद कर सकती हूँ?"
                    elif lang == "en":
                        reply = f"Congratulations! Your appointment has been successfully booked and confirmed. Your booking reference number is {context.booking_reference}. Can I help you with anything else today?"
                    else:
                        reply = f"Badhai ho! Aapki appointment successfully book ho gayi hai. Booking reference number hai {context.booking_reference}. Kya main kisi aur cheez me help kar sakti hoon?"

                    context.history.append({"role": "assistant", "content": reply})
                    return reply, "BOOKING_SUCCESS", book_res
                
                elif book_res.get("status") == "conflict":
                    if lang == "hi":
                        reply = f"माफ़ कीजियेगा, यह स्लॉट अभी किसी अन्य मरीज द्वारा बुक हो गया है। कृपया कोई दूसरा समय चुनें।"
                    elif lang == "en":
                        reply = f"Sorry, this time slot was just booked by another patient. Please choose an alternate slot."
                    else:
                        reply = f"Sorry, yeh time slot abhi kisi doosre patient ne book kar liya. Please doosra slot select karein."

                    context.appointment_time = None
                    context.current_state = ConversationState.SELECT_TIME
                    context.history.append({"role": "assistant", "content": reply})
                    return reply, "DOUBLE_BOOKING_PREVENTED", book_res

                else:
                    reply = f"Booking could not be completed: {book_res.get('message', 'Please try again.')}"
                    context.history.append({"role": "assistant", "content": reply})
                    return reply, "BOOKING_FAILED", book_res

            elif DeterministicNLP.is_rejected(t_cleaned):
                if lang == "hi":
                    reply = "ठीक है, बुकिंग रोक दी गई है। क्या आप डॉक्टर, तारीख या समय बदलना चाहते हैं?"
                elif lang == "en":
                    reply = "Alright, the booking has been cancelled. Would you like to change the doctor, date, or time?"
                else:
                    reply = "Theek hai, booking hold par rakh di gayi hai. Kya aap date ya doctor change karna chahte hain?"

                context.current_state = ConversationState.IDENTIFY_INTENT
                context.history.append({"role": "assistant", "content": reply})
                return reply, "BOOKING_CANCELLED_BY_USER", {}

        # Fallback closure / general turn
        if lang == "hi":
            reply = f"एपेक्स हॉस्पिटल में कॉल करने के लिए धन्यवाद। क्या आपके पास कोई और सवाल है?"
        elif lang == "en":
            reply = f"Thank you for calling Apex Hospital. Do you have any further questions?"
        else:
            reply = f"Apex Hospital me call karne ke liye thank you. Koi aur inquiry hai kya aapki?"

        context.history.append({"role": "assistant", "content": reply})
        return reply, "GENERAL_TURN", {}


# Global agent instance
receptionist_agent = HospitalReceptionistAgent()
