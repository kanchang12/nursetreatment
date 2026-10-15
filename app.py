import os
import json
import sqlite3
import torch
from flask import Flask, render_template, request, jsonify
from google import genai
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# --- PYTORCH 2.6+ WEIGHTS_ONLY PATCH ---
_original_torch_load = torch.load
def _patched_torch_load(*args, **kwargs):
    if 'weights_only' not in kwargs:
        kwargs['weights_only'] = False
    return _original_torch_load(*args, **kwargs)
torch.load = _patched_torch_load
# --------------------------------------

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY"))

DB_PATH = "decagon_index.db"

def query_db(query, params=()):
    if not os.path.exists(DB_PATH):
        return []
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        print(f"[DB ERROR] {e}")
        return []

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/evaluate', methods=['POST'])
def clinical_evaluate():
    req_data = request.json or {}
    
    patient_id = req_data.get('patient_id', '').strip()
    age = req_data.get('age', '')
    gender = req_data.get('gender', '')
    comorbidities = req_data.get('comorbidities', '')
    symptoms = req_data.get('symptoms', '')
    medications = req_data.get('medications', '')
    has_imaging = req_data.get('has_imaging', False)

    # 1. Query Real Synthea Patient Data from SQLite
    matched_patient = None
    patient_meds = []
    patient_conditions = []
    patient_observations = []

    if patient_id:
        pat_rows = query_db("SELECT * FROM patients WHERE id LIKE ? LIMIT 1", (f"%{patient_id}%",))
        if pat_rows:
            matched_patient = pat_rows[0]
            uuid = matched_patient.get('id')
            
            patient_meds = query_db("SELECT * FROM medications WHERE patient = ?", (uuid,))
            patient_conditions = query_db("SELECT * FROM conditions WHERE patient = ?", (uuid,))
            patient_observations = query_db("SELECT * FROM observations WHERE patient = ? LIMIT 15", (uuid,))

    # 2. Query Real Decagon Graph Interactions for active medications
    matched_interactions = []
    if medications:
        med_tokens = [m.strip() for m in medications.split(',')]
        for token in med_tokens:
            if len(token) > 2:
                # Search across decagon interaction table columns
                hits = query_db(
                    "SELECT * FROM decagon_interactions WHERE CAST(zine AS TEXT) LIKE ? OR CAST(gene AS TEXT) LIKE ? LIMIT 5", 
                    (f"%{token}%", f"%{token}%")
                )
                if hits:
                    matched_interactions.extend(hits)

    local_context = {
        "matched_synthea_patient": matched_patient or {"id": patient_id, "note": "Evaluated via manual form fields"},
        "local_csv_medications": patient_meds,
        "local_csv_conditions": patient_conditions,
        "local_csv_observations": patient_observations,
        "queried_decagon_graph_interactions": matched_interactions[:10]
    }

    prompt = f"""
    You are an expert Clinical Decision Support System (CDSS) for nurses operating under NHS/NICE guidelines.
    Evaluate the patient using STRICTLY the indexed local datasets below.

    CRITICAL SAFETY & PROTOCOL RULES:
    1. Do NOT prescribe fixed doses or exact milligram stats without local protocol reference.
    2. Do NOT prescribe oxygen as a blanket instruction unless hypoxia/respiratory distress is evidenced.
    3. Frame transfusion targets around restrictive practice (e.g., Hb ~70 g/L).
    4. Explicitly state whether the local Decagon graph or relational tables verified the interaction.

    === INDEXED LOCAL DATASET EXTRACTION ===
    {json.dumps(local_context, indent=2)}
    ========================================

    Patient Intake Form:
    - ID: {patient_id}
    - Age: {age}, Gender: {gender}
    - Comorbidities: {comorbidities}
    - Presenting Symptoms: {symptoms}
    - Active Medications: {medications}
    - Imaging Available: {'Yes' if has_imaging else 'No'}

    Return your response strictly in raw JSON matching this schema:
    {{
      "ai_message": "Targeted follow-up questions for missing clinical details",
      "clinical_impression": "Concise summary of suspected condition and risk stratification grounded in local data",
      "urgency_and_escalation": ["Immediate escalation steps, ABCDE assessment, senior review"],
      "investigations": ["Required lab and diagnostic orders aligned with local protocol"],
      "management_principles": ["Protocol-guided resuscitation and transfusion/fluid principles"],
      "medication_safety": ["Medication withholding/reversal guidance following local protocol"],
      "graph_evidence_status": "Explicit statement regarding local Decagon graph verification status"
    }}
    Return ONLY valid raw JSON. No markdown backticks.
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]

        parsed_json = json.loads(raw_text.strip())
        return jsonify({"status": "success", "data": parsed_json})
    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def clinical_chat():
    req_data = request.json or {}
    conversation_history = req_data.get('history', [])

    system_prompt = f"""
    You are an expert Clinical Decision Support System (CDSS) for nurses operating under NHS/NICE guidelines.
    Continue the ongoing clinical evaluation dialogue based on the conversation history provided.

    CRITICAL SAFETY & PROTOCOL RULES:
    1. Do NOT prescribe fixed doses or blanket oxygen instructions.
    2. Respond to the nurse's latest answer, refine your clinical impression or management steps, and ask further targeted questions if details are still missing.

    Return your response strictly in raw JSON matching this schema:
    {{
      "ai_message": "Your conversational clinical feedback or next follow-up question",
      "clinical_impression": "Updated summary of condition and risk stratification",
      "urgency_and_escalation": ["escalation step 1", "step 2"],
      "investigations": ["lab 1", "lab 2"],
      "management_principles": ["principle 1"],
      "medication_safety": ["safety point 1"],
      "graph_evidence_status": "Explicit statement regarding local graph query status"
    }}
    Return ONLY valid raw JSON. No markdown backticks.
    """

    messages_payload = [{"role": "user", "text": system_prompt}]
    for msg in conversation_history:
        messages_payload.append({"role": msg["role"], "text": msg["text"]})

    try:
        prompt_str = "\n".join([f"{m['role'].upper()}: {m['text']}" for m in messages_payload])
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt_str
        )
        raw_text = response.text.strip()
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]

        parsed_json = json.loads(raw_text.strip())
        return jsonify({"status": "success", "data": parsed_json})
    except Exception as e:
        print(f"[ERROR] {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)