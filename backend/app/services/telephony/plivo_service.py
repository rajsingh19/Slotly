from typing import Dict, Any, Optional
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class PlivoService:
    """
    Plivo Telephony Integration Service.
    Handles inbound calls, voice XML (Plivo XML) response generation,
    speech capture configuration, and forwarding calls to human receptionists.
    """

    def is_enabled(self) -> bool:
        return settings.PLIVO_ENABLED and bool(settings.PLIVO_AUTH_ID and settings.PLIVO_AUTH_TOKEN)

    def generate_welcome_xml(self, callback_url: str) -> str:
        """
        Generate Plivo XML to greet caller and start capturing speech.
        """
        action_url = f"{settings.PLIVO_APP_URL.rstrip('/')}/api/v1/telephony/plivo/event"
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak voice="WOMAN" language="en-IN">Thank you for calling {settings.HOSPITAL_NAME}. I am Maya, the virtual receptionist. How can I help you today?</Speak>
    <GetSpeech action="{action_url}" method="POST" timeout="5" speechEndTimeout="1" language="en-IN">
        <Speak voice="WOMAN" language="en-IN">Please speak after the tone.</Speak>
    </GetSpeech>
</Response>"""
        return xml

    def generate_reply_xml(self, reply_text: str, continue_conversation: bool = True) -> str:
        """
        Generate Plivo XML for spoken response.
        """
        action_url = f"{settings.PLIVO_APP_URL.rstrip('/')}/api/v1/telephony/plivo/event"
        if continue_conversation:
            xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak voice="WOMAN" language="en-IN">{reply_text}</Speak>
    <GetSpeech action="{action_url}" method="POST" timeout="5" speechEndTimeout="1" language="en-IN"/>
</Response>"""
        else:
            xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak voice="WOMAN" language="en-IN">{reply_text}</Speak>
    <Hangup/>
</Response>"""
        return xml

    def generate_transfer_xml(self, desk_phone: str = "+1-800-555-0199") -> str:
        """
        Transfer call to emergency department or human hospital staff.
        """
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Speak voice="WOMAN" language="en-IN">Please hold while I transfer you to the duty nurse.</Speak>
    <Dial>
        <Number>{desk_phone}</Number>
    </Dial>
</Response>"""
        return xml


plivo_service = PlivoService()
