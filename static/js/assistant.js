"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const languages = {en: "en-IN", hi: "hi-IN", ta: "ta-IN", kn: "kn-IN"};
  const prompts = {
    en: "Ask about sepsis biology, model metrics, Flask APIs, or ESP32 data flow…",
    hi: "सेप्सिस, मॉडल मेट्रिक्स, Flask API या ESP32 डेटा फ्लो के बारे में पूछें…",
    ta: "செப்சிஸ், மாடல் அளவீடுகள், Flask API அல்லது ESP32 தரவு ஓட்டம் பற்றி கேளுங்கள்…",
    kn: "ಸೆಪ್ಸಿಸ್, ಮಾದರಿ ಮೆಟ್ರಿಕ್‌ಗಳು, Flask API ಅಥವಾ ESP32 ಡೇಟಾ ಹರಿವು ಕುರಿತು ಕೇಳಿ…"
  };
  const messages = $("chatMessages");
  const textarea = $("assistantMessage");
  const avatar = $("assistantAvatar");
  let recognition = null;
  function bubble(role, title, text) {
    const box = document.createElement("div");
    box.className = `chat-bubble ${role === "user" ? "user-bubble" : "assistant-bubble"}`;
    const strong = document.createElement("strong"); strong.textContent = title;
    const paragraph = document.createElement("p"); paragraph.textContent = text;
    box.append(strong, paragraph);
    if (role !== "user") {
      const actions = document.createElement("div"); actions.style.display = "flex"; actions.style.gap = "8px"; actions.style.marginTop = "10px";
      const readButton = document.createElement("button"); readButton.type = "button"; readButton.className = "btn btn-ghost btn-small"; readButton.textContent = "🔊 Read aloud";
      readButton.addEventListener("click", () => speak(text));
      const copyButton = document.createElement("button"); copyButton.type = "button"; copyButton.className = "btn btn-ghost btn-small"; copyButton.textContent = "Copy answer";
      copyButton.addEventListener("click", async () => {
        try { await navigator.clipboard.writeText(text); copyButton.textContent = "Copied"; }
        catch { copyButton.textContent = "Copy unavailable"; }
      });
      actions.append(readButton, copyButton); box.append(actions);
    }
    messages.append(box); messages.scrollTop = messages.scrollHeight; return box;
  }
  function speak(text) {
    if (!("speechSynthesis" in window)) { $("voiceStatus").textContent = "Text-to-speech is not supported in this browser."; return; }
    window.speechSynthesis.cancel();
    const lang = languages[$("assistantLanguage").value] || "en-IN";
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = lang; utterance.rate = 0.96;
    const voices = window.speechSynthesis.getVoices();
    const prefix = lang.split("-")[0];
    const voice = voices.find(item => item.lang.toLowerCase() === lang.toLowerCase()) || voices.find(item => item.lang.toLowerCase().startsWith(prefix));
    if (voice) utterance.voice = voice;
    utterance.onstart = () => { avatar.classList.add("speaking"); $("voiceStatus").textContent = `Speaking (${lang}). Mouth movement is an approximate visual cue.`; };
    utterance.onend = utterance.onerror = () => { avatar.classList.remove("speaking"); };
    window.speechSynthesis.speak(utterance);
  }
  $("assistantLanguage")?.addEventListener("change", () => { textarea.placeholder = prompts[$("assistantLanguage").value] || prompts.en; });
  $("assistantForm")?.addEventListener("submit", async event => {
    event.preventDefault();
    const message = textarea.value.trim(); if (!message) return;
    const mode = $("assistantMode").value; const language = $("assistantLanguage").value;
    bubble("user", "You", message); textarea.value = "";
    const button = $("assistantSendButton"); const error = $("assistantError");
    button.disabled = true; button.textContent = "Thinking…"; error.textContent = "";
    avatar.classList.add("listening");
    const pending = bubble("assistant", "SepsisSense Guide", "Thinking…");
    try {
      const response = await fetch("/api/assistant", {method: "POST", headers: {"Content-Type": "application/json", Accept: "application/json"}, body: JSON.stringify({message, language, mode})});
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Assistant request failed.");
      pending.remove(); bubble("assistant", mode === "project" ? "Project consultant" : "Sepsis education guide", `${data.answer}\n\n${data.disclaimer || "Educational information only."}`);
    } catch (err) {
      pending.remove(); const text = err.message.includes("not configured") || err.message.includes("LLM_API_KEY")
        ? "The chat interface is ready, but live AI responses are not configured on the server. Set LLM_API_KEY and LLM_MODEL in Render environment variables, then redeploy. You can still explore the educational pages and project metadata without this integration."
        : `The assistant request failed: ${err.message}`;
      bubble("assistant", "Configuration / connection notice", text); error.textContent = text;
    } finally { button.disabled = false; button.textContent = "Send question →"; avatar.classList.remove("listening"); }
  });
  $("stopSpeechButton")?.addEventListener("click", () => { if ("speechSynthesis" in window) window.speechSynthesis.cancel(); avatar.classList.remove("speaking"); $("voiceStatus").textContent = "Audio stopped."; });
  $("voiceInputButton")?.addEventListener("click", () => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) { $("voiceStatus").textContent = "Speech recognition is not supported in this browser. Type your question instead."; return; }
    if (recognition) { recognition.stop(); recognition = null; }
    recognition = new SpeechRecognition(); recognition.lang = languages[$("assistantLanguage").value] || "en-IN"; recognition.interimResults = true; recognition.continuous = false;
    recognition.onstart = () => { avatar.classList.add("listening"); $("voiceStatus").textContent = `Listening in ${recognition.lang}…`; };
    recognition.onresult = event => { let text = ""; for (let i = event.resultIndex; i < event.results.length; i++) text += event.results[i][0].transcript; textarea.value = text; };
    recognition.onerror = event => { $("voiceStatus").textContent = `Speech recognition error: ${event.error}. You can type instead.`; };
    recognition.onend = () => { avatar.classList.remove("listening"); if ($( "voiceStatus").textContent.startsWith("Listening")) $("voiceStatus").textContent = "Transcript ready. Review it and press Send question."; recognition = null; };
    try { recognition.start(); } catch { $("voiceStatus").textContent = "Microphone could not start. Check browser permissions."; }
  });
  document.querySelectorAll(".prompt-chip").forEach(button => button.addEventListener("click", () => { textarea.value = button.dataset.prompt || ""; textarea.focus(); }));
})();
