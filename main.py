from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
import mysql.connector
import os
import requests
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv

# 🔐 Load .env variables (ensure .env exists and python-dotenv is installed)
load_dotenv()

# Load Hugging Face API key
HUGGINGFACE_API_KEY = os.getenv("HF_API_KEY")
if not HUGGINGFACE_API_KEY:
    raise RuntimeError("Missing HF_API_KEY in environment variables.")

# 🔧 Init FastAPI app
app = FastAPI()

# 📡 Hugging Face Zephyr model API call
def generate_ai_response(prompt: str) -> str:
    url = "https://api-inference.huggingface.co/models/google/flan-t5-small"

    headers = {
        "Authorization": f"Bearer {HUGGINGFACE_API_KEY}"
    }
    payload = {
        "inputs": prompt,
        "parameters": {
            "temperature": 0.7,
            "max_new_tokens": 200
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        result = response.json()
    except Exception as e:
        raise RuntimeError(f"Failed to contact Hugging Face API: {str(e)}")

    if isinstance(result, list) and "generated_text" in result[0]:
        return result[0]["generated_text"].split("Assistant:")[-1].strip()
    elif isinstance(result, dict) and "error" in result:
        raise RuntimeError(f"Model error: {result['error']}")
    else:
        raise RuntimeError("Unexpected API response format.")

# 📄 Patient input schema
class PatientInput(BaseModel):
    name: str
    age: int
    weight: float
    height: float
    allergies: str
    medical_history: str
    symptoms: str

# 🔌 MySQL connection utility
def get_connection():
    try:
        return mysql.connector.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", "root"),
            database=os.getenv("DB_NAME", "prescription")
        )
    except mysql.connector.Error as err:
        raise HTTPException(status_code=500, detail=f"Database connection failed: {str(err)}")

# ──────────────────────────────── ROUTES ─────────────────────────────────

@app.get("/")
def home():
    return {"message": "API is running!"}

@app.get("/test-db")
def test_db():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT DATABASE();")
        db_name = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        return {"message": f"Connected to database: {db_name}"}
    except Exception as e:
        return {"error": str(e)}

@app.post("/submit")
def submit_patient(data: PatientInput):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Insert patient info
        cursor.execute("""
            INSERT INTO patients (name, age, weight, height, allergies, medical_history, symptoms)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (data.name, data.age, data.weight, data.height, data.allergies, data.medical_history, data.symptoms))
        conn.commit()
        patient_id = cursor.lastrowid

        # Generate AI medical text
        prompt = f"""
Patient is a {data.age}-year-old with symptoms: {data.symptoms}.
Medical history: {data.medical_history}.
Allergies: {data.allergies}.

Generate:
1. A summary of the patient's condition
2. Possible treatment options
3. Recommended medications
"""
        ai_output = generate_ai_response(prompt)

        # Save AI response
        cursor.execute("""
            INSERT INTO prescriptions (patient_id, ai_summary, treatment_options, medication_recommendations)
            VALUES (%s, %s, %s, %s)
        """, (patient_id, ai_output, ai_output, ai_output))
        conn.commit()

        cursor.close()
        conn.close()

        return {
            "message": "Patient and AI-powered prescription saved.",
            "patient_id": patient_id
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chatbot")
def chatbot_query(payload: dict = Body(...)):
    patient_id = payload.get("patient_id")
    user_message = payload.get("message")

    if not patient_id or not user_message:
        raise HTTPException(status_code=400, detail="Both 'patient_id' and 'message' are required.")

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT p.name, p.age, p.allergies, p.medical_history, p.symptoms,
                   r.ai_summary, r.treatment_options, r.medication_recommendations
            FROM patients p
            JOIN prescriptions r ON p.id = r.patient_id
            WHERE p.id = %s
        """, (patient_id,))
        row = cursor.fetchone()

        cursor.close()
        conn.close()

        if not row:
            raise HTTPException(status_code=404, detail="Patient not found.")

        # Chatbot prompt
        prompt = f"""
You are an AI medical assistant. A doctor is reviewing a case with the following patient data:

Patient Name: {row['name']}
Age: {row['age']}
Symptoms: {row['symptoms']}
Medical History: {row['medical_history']}
Allergies: {row['allergies']}

AI-Generated Summary: {row['ai_summary']}
AI Treatment Options: {row['treatment_options']}
AI Medication Recommendations: {row['medication_recommendations']}

The doctor asks: {user_message}

Respond clearly and concisely as if advising a medical team.
"""
        reply = generate_ai_response(prompt)
        return {"reply": reply.strip()}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 🌐 Static file serving (e.g. chatbot.html)
app.mount("/static", StaticFiles(directory="static"), name="static")
