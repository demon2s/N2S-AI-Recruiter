import os, fitz, docx, mysql.connector, re, time
from openai import OpenAI
from dotenv import load_dotenv # PUDHUSA ADD PANNADHU

# .env file-la irukka passwords-ah Python-kulla load panrom
load_dotenv()

# 1. Setup
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
db = mysql.connector.connect(
    host="localhost", user="root", password=os.getenv("DB_PASSWORD"), database="resume_project"
)
cursor = db.cursor()

def clean_and_extract(ai_response):
    """Build a tool that cleans up AI responses and returns exactly 4 items."""
    try:
        parts = [p.strip() for p in ai_response.split('|')]
        
        if len(parts) >= 4:
            name = parts[0]
            role = parts[1]
            exp_text = re.findall(r'\d+', parts[2])
            experience = int(exp_text[0]) if exp_text else 0
            location = parts[3][:10]
            return name, role, experience, location
        return None
    except Exception as e:
        return None

def get_expert_details(text, filename):
    prompt = f"""
    Analyze this resume for recruitment:
    1. Name: Candidate Full Name.
    2. Role: Primary or Most Recent Job Title.
    3. Experience: Total years (Only the number).
    4. Location: Current US State Code (e.g., NY, NJ, MI).

    Text: {text[:5000]}
    Return format strictly as: Name | Role | Experience | Location
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        return response.choices[0].message.content.strip()
    except:
        return "Unknown | General | 0 | USA"

# 2. Folder Processing
path = r"C:\Users\LENOVO\OneDrive\Desktop\RECRUIMENT_PROJECT\ALL_RESUME"
files = [f for f in os.listdir(path) if f.lower().endswith(('.pdf', '.docx'))]

print(f"🚀 Processing {len(files)} resumes with Advanced Cleaning...")

for filename in files:
    full_path = os.path.join(path, filename)
    try:
        content = ""
        if filename.lower().endswith(".pdf"):
            with fitz.open(full_path) as doc: content = " ".join([p.get_text() for p in doc])
        else:
            doc = docx.Document(full_path); content = "\n".join([p.text for p in doc.paragraphs])
        
        if content.strip():
            raw_ai_data = get_expert_details(content, filename)
            extracted = clean_and_extract(raw_ai_data)
            
            if extracted:
                name, role, exp, loc = extracted
                sql = "INSERT INTO candidates (name, role, experience, location, filename, resume_text) VALUES (%s, %s, %s, %s, %s, %s)"
                cursor.execute(sql, (name, role, exp, loc, filename, content))
                db.commit()
                print(f"✅ Success: {name} | {role} | {loc} | {exp} Yrs")
            else:
                print(f"⚠️ Parsing Failed for {filename}: {raw_ai_data}")
                
    except Exception as e:
        print(f"❌ Critical Error in {filename}: {e}")

print("\n--- MASTER EXTRACTION COMPLETE! ---")
cursor.close(); db.close()