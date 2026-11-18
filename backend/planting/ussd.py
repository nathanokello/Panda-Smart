"""Africa's Talking USSD simulator.

Uses the same service functions as the REST views and keeps state in UssdSession.
Menus are at most three levels deep (architecture.md Section 6.5).
"""
from core import services as core_services
from core.phone import normalize_phone
from planting.models import PlantingIntent, UssdSession
from planting import services as planting_services
from records import services as records_services


def _select(options, choice):
    try:
        index = int(choice) - 1
    except (TypeError, ValueError):
        return None
    return options[index] if 0 <= index < len(options) else None


# Africa's Talking shows at most about 182 characters per USSD screen.
MAX_USSD_CHARS = 182


def _fit(response: str) -> str:
    if len(response) <= MAX_USSD_CHARS:
        return response
    return response[: MAX_USSD_CHARS - 1].rstrip() + "…"


def handle_ussd(session_id: str, phone: str, text: str) -> str:
    return _fit(_handle(session_id, normalize_phone(phone), text))


def _handle(session_id: str, phone: str, text: str) -> str:
    parts = [part.strip() for part in (text or "").split("*") if part.strip()]
    session, _ = UssdSession.objects.get_or_create(
        session_id=session_id, defaults={"phone": phone, "state": "", "data": {}}
    )
    session.phone = phone
    session.state = "*".join(parts)[:50]  # field is max_length=50
    session.data = {"menu": parts[0] if parts else "root"}
    session.save(update_fields=["phone", "state", "data"])

    if not parts:
        return "CON Panda Smart\n1 Planting advice\n2 My planting slot\n3 Verify my grain"

    if parts[0] == "1":
        wards = core_services.list_wards(limit=9)
        if len(parts) == 1:
            menu = "\n".join(f"{index + 1} {ward.name}" for index, ward in enumerate(wards))
            return f"CON Select ward:\n{menu}"
        ward = _select(wards, parts[1])
        if not ward:
            return "END Invalid ward. Dial again."
        crops = core_services.list_crops()
        if len(parts) == 2:
            menu = "\n".join(f"{index + 1} {crop.name_en}" for index, crop in enumerate(crops))
            return f"CON Select crop:\n{menu}"
        crop = _select(crops, parts[2])
        if not crop:
            return "END Invalid crop. Dial again."
        advice = planting_services.get_advice(ward, crop)
        window = advice["recommended_window"]
        return (
            f"END {crop.name_en}: {window['start']} to {window['end']}. "
            f"Confidence {advice['confidence']:.0%}. {advice['rationale']}"
        )

    if parts[0] == "2":
        farmer = core_services.get_farmer_by_phone(phone)
        if not farmer:
            return "END No farmer found for this phone number."
        intents = PlantingIntent.objects.filter(farmer=farmer).select_related("slot", "crop")
        if not intents:
            return "END You have no planting slot yet. Register an intent first."
        lines = [
            f"{intent.crop.name_en}: "
            + (
                f"{intent.slot.window_start} to {intent.slot.window_end}"
                if intent.slot
                else "slot pending"
            )
            for intent in intents[:3]
        ]
        return "END " + " | ".join(lines)

    if parts[0] == "3":
        links = records_services.get_verification_links_for_phone(phone)
        if not links:
            return "END No active verification link. Contact your storage agent."
        return "END Open your verify link: " + links[0]

    return "END Invalid selection. Dial again."
