"use strict";

document.addEventListener("DOMContentLoaded", () => {
  // 1. 4-Stage Interactive Progression
  const stages = {
    1: {
      title: "Stage 1: Primary Infection & Pathogen Recognition",
      body: "The process begins when pathogens breach physical barriers (lungs, abdomen, catheter, urinary tract). Microbial components (PAMPs) such as lipopolysaccharide (LPS) bind to Toll-like Receptors (TLRs) on resident macrophages and dendritic cells.",
      vitals: "Physiological Correlate: Mild to moderate tachycardia (elevated HR), fever or early chills as hypothalamic setpoint shifts.",
    },
    2: {
      title: "Stage 2: Host Hyper-Inflammation (Cytokine Storm)",
      body: "Activated immune cells release an explosive cascade of pro-inflammatory mediators (TNF-α, IL-1β, IL-6). Rather than remaining localized, the response escapes local containment and disseminates throughout the systemic circulation.",
      vitals: "Physiological Correlate: Pronounced tachycardia (>90 BPM), tachypnea (>20 breaths/min), elevated temperature (>38°C) or profound hypothermia (<36°C).",
    },
    3: {
      title: "Stage 3: Endothelial Breakdown & Microvascular Damage",
      body: "Cytokines disrupt vascular endothelial junction proteins (VE-cadherin), causing widespread capillary leak. Plasma proteins extravasate into tissue spaces, precipitating severe intravascular volume depletion and systemic vasodilation.",
      vitals: "Physiological Correlate: Arterial hypotension, decreased oxygen saturation (SpO2 drops as pulmonary edema impairs alveolar gas exchange), cool or clammy extremities.",
    },
    4: {
      title: "Stage 4: Tissue Hypoperfusion & Multiorgan Dysfunction (MODS)",
      body: "Microthrombi (DIC) clog capillaries, impeding oxygen delivery. Cellular hypoxia and mitochondrial poisoning prevent ATP synthesis, leading to anaerobic metabolism, high serum lactate, acute kidney injury, encephalopathy, and cardiovascular collapse.",
      vitals: "Physiological Correlate: Critical hypoxemia, refractory hypotension, altered mental status, oliguria, potentially fatal septic shock.",
    },
  };

  const stageNodes = document.querySelectorAll("#progressionFlow .pipeline-node");
  const stageTitle = document.getElementById("stageTitle");
  const stageBody = document.getElementById("stageBody");
  const stageVitals = document.getElementById("stageClinicalVitals");

  stageNodes.forEach((node) => {
    node.addEventListener("click", () => {
      stageNodes.forEach((n) => n.classList.remove("active"));
      node.classList.add("active");
      const stageId = node.getAttribute("data-stage");
      const data = stages[stageId];
      if (data && stageTitle && stageBody && stageVitals) {
        stageTitle.textContent = data.title;
        stageBody.textContent = data.body;
        stageVitals.innerHTML = `<strong>Physiological Correlate:</strong> ${data.vitals}`;
      }
    });
  });

  // 2. Concept Selector
  const concepts = {
    innate: {
      title: "Innate vs. Adaptive Immune Dysregulation",
      body: "Early sepsis features hyper-activation of innate immunity (neutrophils, monocytes, cytokines) alongside rapid apoptosis of lymphocytes (T-cells, B-cells). This leads to a paradoxical state of concurrent hyper-inflammation and severe immune exhaustion.",
    },
    endothelial: {
      title: "Endothelial Barrier Breakdown & Capillary Leak",
      body: "Normal vascular endothelium maintains fluid balance and prevents thrombosis. In sepsis, glycocalyx degradation and loss of tight junctions allow plasma to flood interstitial spaces, leading to hypovolemia, tissue edema, and impaired nutrient exchange.",
    },
    coagulation: {
      title: "Coagulation Activation & Microthrombi",
      body: "Tissue factor exposure on injured endothelium triggers systemic thrombin generation. Fibrin clots form in small arterioles and capillaries, occluding blood flow to vital organs while consuming platelets, predisposing patients to concurrent bleeding and thrombosis.",
    },
    mitochondrial: {
      title: "Mitochondrial Dysfunction & Cytopathic Hypoxia",
      body: "Even when arterial oxygenation is artificially maintained, cells cannot utilize oxygen due to mitochondrial damage from reactive oxygen species (ROS) and nitric oxide. This is termed 'cytopathic hypoxia' and causes metabolic failure.",
    },
    vitals: {
      title: "Why Sensor Vitals Alone Cannot Diagnose Sepsis",
      body: "Heart rate, SpO2, and temperature reflect generic systemic stress. They can be triggered by anxiety, exercise, mild dehydration, or non-infectious trauma. Sepsis diagnosis fundamentally requires evidence of infection paired with acute organ dysfunction.",
    },
  };

  const bioSelect = document.getElementById("bioConceptSelect");
  const bioTitle = document.getElementById("bioConceptTitle");
  const bioBody = document.getElementById("bioConceptBody");

  if (bioSelect && bioTitle && bioBody) {
    bioSelect.addEventListener("change", (e) => {
      const item = concepts[e.target.value];
      if (item) {
        bioTitle.textContent = item.title;
        bioBody.textContent = item.body;
      }
    });
  }

  // 3. Glossary Filter
  const glossarySearch = document.getElementById("glossarySearch");
  const glossaryItems = document.querySelectorAll(".glossary-item");

  if (glossarySearch) {
    glossarySearch.addEventListener("input", (e) => {
      const q = e.target.value.toLowerCase().trim();
      glossaryItems.forEach((item) => {
        const text = item.textContent.toLowerCase();
        const term = item.getAttribute("data-term") || "";
        if (text.includes(q) || term.includes(q)) {
          item.style.display = "block";
        } else {
          item.style.display = "none";
        }
      });
    });
  }

  // 4. Biology Quiz Form
  const bioQuizForm = document.getElementById("bioQuizForm");
  const quizFeedback = document.getElementById("quizFeedback");

  if (bioQuizForm && quizFeedback) {
    bioQuizForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const q1 = bioQuizForm.elements["q1"]?.value;
      const q2 = bioQuizForm.elements["q2"]?.value;

      let score = 0;
      let total = 2;

      if (q1 === "correct") score++;
      if (q2 === "correct") score++;

      quizFeedback.style.display = "block";
      if (score === total) {
        quizFeedback.style.background = "rgba(34, 197, 94, 0.12)";
        quizFeedback.style.border = "1px solid rgba(34, 197, 94, 0.3)";
        quizFeedback.style.color = "var(--green-400)";
        quizFeedback.innerHTML = `<strong>Outstanding! ${score}/${total} Correct.</strong> You demonstrate a solid grasp of sepsis pathophysiology and vital-sign interpretation.`;
      } else {
        quizFeedback.style.background = "rgba(245, 158, 11, 0.12)";
        quizFeedback.style.border = "1px solid rgba(245, 158, 11, 0.3)";
        quizFeedback.style.color = "var(--amber-400)";
        quizFeedback.innerHTML = `<strong>Result: ${score}/${total} Correct.</strong> Review the questions above. Remember that hypothermia is a dangerous sign of shock, and sensor vitals cannot replace clinical laboratory testing.`;
      }

      // Save quiz attempt silently
      fetch("/api/quiz/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ quiz_topic: "biology", score: score, total: total }),
      }).catch(() => {});
    });
  }
});
