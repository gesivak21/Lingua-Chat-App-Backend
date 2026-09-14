from fastapi import HTTPException, APIRouter, Depends
from googletrans import Translator

from database import get_last_message
from auth import get_current_user


router = APIRouter()

translator = Translator()


# ============================================================
# TRANSLATION
# ============================================================

def translate_text(
    text: str,
    target_language: str
) -> str:

    try:
        result = translator.translate(
            text,
            dest=target_language
        )

        return result.text

    except Exception as e:
        print("Translation error:", repr(e))
        return text


# ============================================================
# TRANSLATE CHAT MESSAGE
# ============================================================

@router.post("/chat_message_translate")
async def chat_message_translate_endpoint(
    request: dict,
    user_mobile: str = Depends(get_current_user)
):

    receiver_mobile = request.get("receiver_mobile")
    message = request.get("message")
    translated_to = request.get(
        "translated_to",
        "en"
    )

    sender_mobile = user_mobile

    # Get last message if no message was provided
    if not message:

        if not receiver_mobile:
            raise HTTPException(
                status_code=400,
                detail="receiver_mobile required"
            )

        last = get_last_message(receiver_mobile)

        if not last:
            raise HTTPException(
                status_code=404,
                detail="No messages found"
            )

        sender_mobile = last["sender_mobile"]
        message = last["message"]

    # Detect language
    try:
        detected = translator.detect(message)
        detected_lang = detected.lang

    except Exception as e:
        print("Language detection error:", repr(e))

        raise HTTPException(
            status_code=500,
            detail=f"Language detection failed: {str(e)}"
        )

    # Translate message
    try:
        translated = translator.translate(
            message,
            dest=translated_to
        )

    except Exception as e:
        print("Translation error:", repr(e))

        raise HTTPException(
            status_code=500,
            detail=f"Translation failed: {str(e)}"
        )

    return {
        "receiver_mobile": receiver_mobile,
        "sender_mobile": sender_mobile,
        "original_message": message,
        "detected_language": detected_lang,
        "target_language": translated_to,
        "translated_message": translated.text
    }
