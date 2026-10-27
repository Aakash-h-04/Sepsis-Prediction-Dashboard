"""
SepsisSense AI Assistant Service
Supports Sepsis Education Mode and Project Consultant Mode.
Full 4-language support: English, Hindi, Tamil, Kannada.
Server-side LLM abstraction supporting OpenAI, Google Gemini, and Groq.
Resilient: Automatically falls back to vetted clinical knowledge if the provider
returns 401, 429, or network errors, ensuring the user experience never breaks.
"""

import json
import logging
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi (हिन्दी)",
    "ta": "Tamil (தமிழ்)",
    "kn": "Kannada (ಕನ್ನಡ)",
}

CURATED_KNOWLEDGE = {
    "en": {
        "what is sepsis": (
            "Sepsis is a medical emergency caused by the body's dysregulated, life-threatening response to an infection. "
            "Instead of fighting off the localized pathogen, the immune system triggers widespread systemic inflammation, "
            "capillary leak, and microvascular blood clotting that can rapidly lead to multiorgan failure and septic shock.\n\n"
            "Recognized warning signs follow the SEPSIS mnemonic:\n"
            "• S — Shivering, severe chills, or extreme fever\n"
            "• E — Extreme body pain or general discomfort\n"
            "• P — Pale, discolored, or clammy skin\n"
            "• S — Sleepiness, altered mental state, or confusion\n"
            "• I — 'I feel like I might die' (a severe feeling of impending doom)\n"
            "• S — Shortness of breath or rapid breathing\n\n"
            "Normal vital signs do NOT rule out sepsis. Suspected sepsis requires urgent hospital evaluation immediately."
        ),
        "symptoms": (
            "Recognized sepsis warning signs include:\n"
            "1. Altered mental status, confusion, or severe lethargy\n"
            "2. Rapid breathing (>20 breaths/min) or shortness of breath\n"
            "3. Elevated heart rate (>90 BPM) or weak peripheral pulse\n"
            "4. Fever (>38°C) or dangerous hypothermia (<36°C)\n"
            "5. Clammy, sweaty, or mottled skin\n"
            "6. Drastic drop in urine output (oliguria)\n\n"
            "If someone with an infection develops any of these signs, seek emergency medical care immediately."
        ),
        "architecture": (
            "SepsisSense is an end-to-end healthcare technology platform:\n"
            "1. Edge Telemetry: ESP32 node measures BPM, Temperature, and SpO2 every 5 seconds, posting JSON to POST /api/readings.\n"
            "2. Web Server: Python Flask on Render, serving the responsive UI, REST API, and session management.\n"
            "3. Inference Pipeline: Scikit-learn Random Forest (200 trees, class_weight='balanced') mapping inputs to [HR, O2Sat, Temp].\n"
            "4. Decision Threshold: Empirically tuned to 0.01 to prioritize sensitivity under extreme class imbalance (~2% positive cases).\n"
            "5. Observability: Live Chart.js telemetry monitor at /dashboard with real-time polling."
        ),
        "model": (
            "The exploratory machine-learning pipeline details:\n"
            "• Classifier: Random Forest (200 estimators) trained on PhysioNet Challenge data.\n"
            "• Feature Order: Heart Rate (HR), Oxygen Saturation (O2Sat), and Body Temperature (Temp).\n"
            "• Test Metrics: Accuracy 59.61%, Precision 3.70%, Recall 55.32%, F1 0.0693, ROC-AUC 0.5854.\n"
            "• Threshold: 0.01 (selected on validation set).\n"
            "• Important: Precision is very low (3.7%) because sepsis is rare in hospital data. This model is an educational engineering prototype, NOT a clinically validated diagnostic tool."
        ),
    },
    "hi": {
        "what is sepsis": (
            "सेप्सिस (Sepsis) एक अत्यंत गंभीर और जानलेवा स्थिति है जो तब उत्पन्न होती है जब किसी संक्रमण के प्रति "
            "शरीर की प्रतिरक्षा प्रणाली अनियंत्रित होकर अपने ही अंगों और ऊतकों को नुकसान पहुँचाने लगती है।\n\n"
            "मुख्य चेतावनी संकेत (SEPSIS):\n"
            "• S — अत्यधिक कंपकंपी या तेज बुखार\n"
            "• E — अत्यधिक शारीरिक दर्द या बेचैनी\n"
            "• P — त्वचा का पीला या चिपचिपा होना\n"
            "• S — अत्यधिक नींद, भ्रम या बेहोशी\n"
            "• I — 'मुझे बहुत बुरा लग रहा है' (गंभीर बेचैनी)\n"
            "• S — तेज सांस चलना या सांस फूलना\n\n"
            "चेतावनी: सामान्य वाइटल संकेत भी सेप्सिस की संभावना को खारिज नहीं करते। तुरंत आपातकालीन चिकित्सा सहायता लें।"
        ),
        "symptoms": (
            "सेप्सिस के मुख्य लक्षण: तेज दिल की धड़कन (>90 BPM), तेज सांस, तेज बुखार या अत्यधिक ठंड लगना (<36°C), "
            "मानसिक भ्रम और पेशाब में भारी कमी। यदि सेप्सिस का संदेह हो, तो तुरंत अस्पताल जाएँ।"
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
    Attempts live LLM inference if credentials exist.
    If LLM request encounters an error (401, timeout, invalid key),
    gracefully returns vetted reference knowledge without crashing.
    """
    if metadata is None:
        metadata = {}

    raw_api_key = os.getenv("LLM_API_KEY")
    if not raw_api_key:
        return _fallback_response(message, language, mode, metadata)

    api_key = raw_api_key.strip().strip("'\"")
    if not api_key:
        return _fallback_response(message, language, mode, metadata)

    # Auto-detect provider endpoint and default model
    base_url = os.getenv("LLM_BASE_URL", "").strip().rstrip("/")
    model = os.getenv("LLM_MODEL", "").strip()

    if not base_url:
        if api_key.startswith("AIzaSy"):
            # Google Gemini OpenAI-compatible endpoint
            base_url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            if not model:
                model = "gemini-1.5-flash"
        elif api_key.startswith("gsk_"):
            # Groq endpoint
            base_url = "https://api.groq.com/openai/v1/chat/completions"
            if not model:
                model = "llama-3.1-8b-instant"
        else:
            # Default to OpenAI
            base_url = "https://api.openai.com/v1/chat/completions"
            if not model:
                model = "gpt-4o-mini"
    else:
        if not model:
            model = "gpt-4o-mini"

    try:
        return _call_llm(message, language, mode, metadata, api_key, model, base_url)
    except Exception as exc:
        logger.warning("Live LLM failed: %s; falling back to curated knowledge base", exc)
        fallback = _fallback_response(message, language, mode, metadata)
        notice = f"*(Note: Live AI provider returned '{exc}'. Displaying verified clinical reference.)*\n\n"
        fallback["answer"] = notice + fallback["answer"]
        fallback["provider"] = f"Curated Reference (Live provider error: {exc})"
        return fallback


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
        "You are SepsisSense AI, an intelligent, authoritative, responsible healthcare education and engineering guide. "
        "CRITICAL DIRECTIVE: You are an EDUCATIONAL TOOL, NOT a medical doctor. "
        "Never diagnose, prescribe, or provide medical clearance. Never claim normal vitals rule out sepsis. "
        "If the user mentions emergency signs, urge immediate emergency hospital care (112, 911, or 999). "
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
            "User-Agent": "SepsisSense-Assistant/2.0",
        },
        method="POST",
    )

    with urlopen(req, timeout=25) as resp:
        result = json.loads(resp.read().decode("utf-8"))
        answer = result["choices"][0]["message"]["content"].strip()
        return {
            "answer": answer,
            "language": language,
            "mode": mode,
            "provider": f"Live LLM ({model})",
            "disclaimer": "Educational and experimental only. Not a medical diagnosis.",
        }


def _fallback_response(message, language, mode, metadata):
    msg_lower = message.lower()
    lang_dict = CURATED_KNOWLEDGE.get(language, CURATED_KNOWLEDGE["en"])

    if any(k in msg_lower for k in ["symptom", "sign", "warning", "लक्षण", "ಅಲಕ್ಷಣ", "அறிகுறி"]):
        answer = lang_dict.get("symptoms", CURATED_KNOWLEDGE["en"]["symptoms"])
    elif any(k in msg_lower for k in ["architecture", "esp32", "api", "route", "flow", "backend", "code"]):
        answer = CURATED_KNOWLEDGE["en"]["architecture"]
    elif any(k in msg_lower for k in ["model", "metric", "precision", "accuracy", "random forest", "threshold"]):
        answer = CURATED_KNOWLEDGE["en"]["model"]
    else:
        answer = lang_dict.get("what is sepsis", CURATED_KNOWLEDGE["en"]["what is sepsis"])

    return {
        "answer": answer,
        "language": language,
        "mode": mode,
        "provider": "SepsisSense Clinical Knowledge Base",
        "disclaimer": "Educational and experimental only. Not a medical diagnosis.",
    }
