"""
SepsisSense AI Assistant Service
Supports Sepsis Education Mode and Project Consultant Mode.
Full 4-language support: English, Hindi, Tamil, Kannada.
Server-side LLM abstraction. When LLM credentials are unconfigured,
provides curated, accurate educational responses with explicit status.
"""

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi (हिन्दी)",
    "ta": "Tamil (தமிழ்)",
    "kn": "Kannada (ಕನ್ನಡ)",
}

# Curated reference responses for offline / unconfigured demo mode
CURATED_KNOWLEDGE = {
    "en": {
        "what is sepsis": (
            "Sepsis is a life-threatening medical emergency that arises when the body's response "
            "to an infection damages its own tissues and organs. It is not an infection itself, "
            "but rather a dysregulated, toxic host response to infection. According to the World Health "
            "Organization (WHO), sepsis accounts for roughly 11 million deaths globally each year.\n\n"
            "Key warning signs include: shivering/extreme chills, high fever or very low body temperature, "
            "rapid heart rate, shortness of breath, extreme pain or discomfort, clammy/sweaty skin, and "
            "confusion or disorientation. If sepsis is suspected, immediate emergency medical care is critical."
        ),
        "symptoms": (
            "Recognized sepsis warning signs often follow the SEPSIS acronym:\n"
            "• S — Shivering, severe fever, or very cold\n"
            "• E — Extreme pain or general discomfort\n"
            "• P — Pale, discolored, or clammy skin\n"
            "• S — Sleepiness, altered mental state, or confusion\n"
            "• I — 'I feel like I might die' (a severe feeling of impending doom)\n"
            "• S — Shortness of breath or rapid breathing\n\n"
            "Normal vital signs do NOT rule out sepsis. Always seek immediate professional evaluation."
        ),
        "architecture": (
            "The SepsisSense platform is built as a unified full-stack architecture:\n"
            "1. IoT Edge (ESP32): Reads vitals (BPM, Temperature, SpO2) and posts to /api/readings.\n"
            "2. Backend: Python Flask on Render, serving the public website, monitoring dashboard, and REST API.\n"
            "3. ML Pipeline: Scikit-learn Random Forest classifier with 200 estimators, trained on PhysioNet Challenge data.\n"
            "4. Feature Ordering: Strict pipeline ordering [HR, O2Sat, Temp]. Incoming API [bpm, temperature, spo2] is mapped.\n"
            "5. Threshold: Configured at 0.01 to favor sensitivity over precision due to high class imbalance."
        ),
        "model": (
            "The machine learning model is an exploratory Scikit-learn Random Forest pipeline:\n"
            "• Features: Heart Rate (HR), Oxygen Saturation (O2Sat), and Body Temperature (Temp).\n"
            "• Decision Threshold: 0.01 (selected on validation set).\n"
            "• Test Metrics: Accuracy ~59.6%, Precision ~3.7%, Recall ~55.3%, F1 ~0.069, ROC-AUC ~0.585.\n"
            "• Important note: Precision is very low (3.7%) due to severe sepsis class imbalance. "
            "This model is an educational engineering prototype, NOT a clinically validated diagnostic tool."
        ),
    },
    "hi": {
        "what is sepsis": (
            "सेप्सिस (Sepsis) एक अत्यंत गंभीर और जानलेवा स्थिति है जो तब उत्पन्न होती है जब किसी संक्रमण के प्रति "
            "शरीर की प्रतिरक्षा प्रणाली अनियंत्रित होकर अपने ही अंगों और ऊतकों को नुकसान पहुँचाने लगती है।\n\n"
            "मुख्य चेतावनी संकेत: अत्यधिक कंपकंपी या तेज बुखार, अत्यधिक पसीना या चिपचिपी त्वचा, तेज दिल की धड़कन, "
            "सांस लेने में कठिनाई, अत्यधिक दर्द और मानसिक भ्रम। यदि सेप्सिस का संदेह हो, तो तुरंत अस्पताल जाएँ।"
        ),
        "symptoms": (
            "सेप्सिस के मुख्य लक्षण:\n"
            "• अत्यधिक ठंड लगना या तेज बुखार\n"
            "• अत्यधिक शारीरिक दर्द या बेचैनी\n"
            "• त्वचा का पीला या चिपचिपा होना\n"
            "• अत्यधिक नींद, भ्रम या बेहोशी जैसी स्थिति\n"
            "• तेज सांस चलना या सांस फूलना\n\n"
            "चेतावनी: सामान्य वाइटल संकेत भी सेप्सिस की संभावना को पूरी तरह खारिज नहीं करते। तत्काल डॉक्टर से संपर्क करें।"
        ),
    },
    "ta": {
        "what is sepsis": (
            "செப்சிஸ் (Sepsis) என்பது உடலில் ஏற்படும் ஒரு தொற்றுநோய்க்கு எதிராக நமது நோயெதிர்ப்பு அமைப்பு "
            "கட்டுப்பாடில்லாமல் செயல்பட்டு, தனது சொந்த உறுப்புகளையே தாக்கும் ஒரு ஆபத்தான மருத்துவ அவசரநிலையாகும்.\n\n"
            "முக்கிய அறிகுறிகள்: கடுமையான நடுக்கம், அதிக காய்ச்சல் அல்லது மிகக் குறைந்த உடல் வெப்பநிலை, விரைவான இதயத் துடிப்பு, "
            "மூச்சுத் திணறல், கடுமையான உடல் வலி, மற்றும் குழப்பமான மனநிலை. செப்சிஸ் சந்தேகம் இருந்தால் உடனடியாக அவசர மருத்துவ உதவியை நாடவும்."
        ),
    },
    "kn": {
        "what is sepsis": (
            "ಸೆಪ್ಸಿಸ್ (Sepsis) ಒಂದು ಜೀವಕ್ಕೆ ಅಪಾಯಕಾರಿಯಾದ ತುರ್ತು ವೈದ್ಯಕೀಯ ಸ್ಥಿತಿಯಾಗಿದ್ದು, ಇದು ದೇಹದಲ್ಲಿನ ಯಾವುದೇ ಸೋಂಕಿಗೆ "
            "ಪ್ರತಿಯಾಗಿ ರೋಗನಿರೋಧಕ ವ್ಯವಸ್ಥೆಯು ಅತಿಯಾಗಿ ಪ್ರತಿಕ್ರಿಯಿಸಿ, ತನ್ನದೇ ಅಂಗಾಂಗಗಳಿಗೆ ಹಾನಿ ಉಂಟುಮಾಡಿದಾಗ ಸಂಭವಿಸುತ್ತದೆ.\n\n"
            "ಮುಖ್ಯ ಲಕ್ಷಣಗಳು: ಅತಿಯಾದ ನಡುಕ ಅಥವಾ ಜ್ವರ, ತೀವ್ರ ದೇಹದ ನೋವು, ಉಸಿರಾಟದ ತೊಂದರೆ, ವೇಗವಾದ ಹೃದಯ ಬಡಿತ, ಮತ್ತು ಗೊಂದಲ. "
            "ಸೆಪ್ಸಿಸ್ ಶಂಕೆ ಇದ್ದರೆ ತಕ್ಷಣವೇ ವೈದ್ಯಕೀಯ ತುರ್ತು ಚಿಕಿತ್ಸೆ ಪಡೆಯಿರಿ."
        ),
    },
}


def answer_question(message, language="en", mode="education", metadata=None):
    """
    Answers a question in the requested language and mode.
    If LLM_API_KEY is present, calls the LLM provider.
    Otherwise, returns an accurate vetted response with configuration instructions.
    """
    if metadata is None:
        metadata = {}

    api_key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    base_url = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1/chat/completions").rstrip("/")

    # If LLM credentials exist, invoke live LLM
    if api_key:
        return _call_llm(message, language, mode, metadata, api_key, model, base_url)

    # Fallback to curated reference knowledge
    return _fallback_response(message, language, mode, metadata)


def _call_llm(message, language, mode, metadata, api_key, model, base_url):
    project_context = {
        "backend": "Python Flask deployed on Render at https://sepsis-prediction-dashboard.onrender.com/",
        "existing_api": "POST /api/readings accepts bpm, temperature, spo2; returns 201 with stored id & prediction",
        "model_features_in_order": metadata.get("features", ["HR", "O2Sat", "Temp"]),
        "target": metadata.get("target", "SepsisLabel"),
        "selected_threshold": metadata.get("selected_threshold", 0.01),
        "test_metrics": metadata.get("test_metrics", {
            "accuracy": 0.596,
            "precision": 0.037,
            "recall": 0.553,
            "f1": 0.069,
            "roc_auc": 0.585,
        }),
        "metadata_note": metadata.get("note", "Model is experimental and not clinically validated."),
    }

    safety_rules = (
        "You are SepsisSense AI, a warm, authoritative, responsible healthcare education and engineering guide. "
        "CRITICAL SAFETY DIRECTIVE: You are an EDUCATIONAL TOOL, NOT a medical doctor. "
        "Never diagnose, prescribe, or provide medical clearance. Never state that normal vitals or a low model score rules out sepsis. "
        "If the user mentions emergency signs (e.g., severe breathlessness, confusion, extreme pain), urge immediate emergency care. "
        f"You MUST reply in {LANGUAGE_NAMES.get(language, 'English')}. "
    )

    if mode == "project":
        system_prompt = (
            safety_rules +
            "You are acting in Project Consultant Mode. Explain the system architecture, Flask routes, ESP32 ingestion, "
            "Random Forest pipeline, feature ordering [HR, O2Sat, Temp], low precision trade-off, and deployment. "
            "Project facts: " + json.dumps(project_context, ensure_ascii=False)
        )
    else:
        system_prompt = (
            safety_rules +
            "You are acting in Sepsis Education Mode. Explain biological mechanisms (dysregulated host response, "
            "pro-inflammatory cytokines, endothelial permeability, organ hypoperfusion), warning signs, and prevention. "
            "Cite WHO (https://www.who.int/news-room/fact-sheets/detail/sepsis) and CDC where appropriate."
        )

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        "temperature": 0.3,
    }).encode("utf-8")

    req = Request(
        base_url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=35) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            answer = result["choices"][0]["message"]["content"].strip()
            return {
                "answer": answer,
                "language": language,
                "mode": mode,
                "provider": "Live LLM (" + model + ")",
                "disclaimer": "Educational and experimental only. Not a medical diagnosis.",
            }
    except HTTPError as exc:
        raise RuntimeError(f"AI provider HTTP {exc.code}") from exc
    except Exception as exc:
        raise RuntimeError(f"AI provider unreachable: {exc}") from exc


def _fallback_response(message, language, mode, metadata):
    """
    Returns high quality vetted answers when live LLM credentials are not configured.
    """
    msg_lower = message.lower()
    lang_dict = CURATED_KNOWLEDGE.get(language, CURATED_KNOWLEDGE["en"])

    # Match topic
    if any(k in msg_lower for k in ["symptom", "sign", "warning", "लक्षण", "ಅಲಕ್ಷಣ", "அறிகுறி"]):
        answer = lang_dict.get("symptoms", CURATED_KNOWLEDGE["en"]["symptoms"])
    elif any(k in msg_lower for k in ["architecture", "esp32", "api", "route", "flow", "backend"]):
        answer = CURATED_KNOWLEDGE["en"]["architecture"]
    elif any(k in msg_lower for k in ["model", "metric", "precision", "accuracy", "random forest", "threshold"]):
        answer = CURATED_KNOWLEDGE["en"]["model"]
    else:
        answer = lang_dict.get("what is sepsis", CURATED_KNOWLEDGE["en"]["what is sepsis"])

    prefix = ""
    if language != "en" and language not in CURATED_KNOWLEDGE:
        prefix = f"[{LANGUAGE_NAMES.get(language, 'Selected language')} reference]\n\n"

    config_note = (
        "\n\n---\n"
        "💡 *Note: SepsisSense AI is currently operating in Curated Reference Mode. "
        "To enable live conversational AI generation, configure LLM_API_KEY and LLM_MODEL in your server environment.*"
    )

    return {
        "answer": prefix + answer + config_note,
        "language": language,
        "mode": mode,
        "provider": "Curated Knowledge Base (LLM unconfigured)",
        "disclaimer": "Educational and experimental only. Not a medical diagnosis.",
    }
