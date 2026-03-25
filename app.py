import streamlit as st
import mysql.connector
import pandas as pd
import os
import json
import warnings
from openai import OpenAI
from sentence_transformers import SentenceTransformer, util
from dotenv import load_dotenv

# --- Setup ---
warnings.filterwarnings('ignore')
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

# Load environment variables (.env)
load_dotenv() 

# Initialize AI and SBERT models
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
ranking_model = SentenceTransformer('all-MiniLM-L6-v2')

def get_db_connection():
    return mysql.connector.connect(
        host="localhost", user="root", password=os.getenv("DB_PASSWORD"), database="resume_project"
    )

# --- The Perfect Match Brain ---
def perfect_match_rules(jd_input, target_loc_input):
    """LLM sets the 4 absolute strict rules for the SQL gatekeeper"""
    prompt = f"""
    Analyze JD: "{jd_input}" and Location: "{target_loc_input}"
    
    1. Find the 2-letter State Code and 3 nearby states.
    2. Identify 3 acceptable Job Titles (e.g., for a Java role: 'Java', 'Backend', 'Software Engineer').
    3. Identify the ONE absolute mandatory technical skill (e.g., 'Kafka' or 'Spring Boot').
    
    Return ONLY JSON:
    {{
        "state_code": "TX",
        "nearby": ["OK", "LA", "NM", "AR"],
        "role_keywords": ["Java", "Backend", "Software Engineer"],
        "mandatory_skill": "Kafka"
    }}
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={ "type": "json_object" }
    )
    return json.loads(response.choices[0].message.content)

@st.fragment
def display_candidate(row):
    """Pure UI - No extra fluff"""
    with st.container():
        c1, c2, c3, c4 = st.columns([1, 4, 2, 2])
        c1.metric("Match", f"{row['AI_Score']}%")
        c2.write(f"👤 **{row['name']}**")
        c2.write(f"💼 {row['role']}")
        c3.write(f"🏢 Exp: {row['experience']} Yrs")
        c3.write(f"📍 Loc: {row['location']}")
        
        file_path = os.path.join(r"C:\Users\LENOVO\OneDrive\Desktop\RECRUIMENT_PROJECT\ALL_RESUME", row['filename'])
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                c4.download_button(label="📥 Download Resume", data=f, file_name=row['filename'], key=f"dl_{row['id']}")
        st.divider()

# --- MAIN UI CONFIGURATION ---
st.set_page_config(page_title="N2S Perfect Resume Matcher", layout="wide", page_icon="🎯")

# --- INJECT CUSTOM CSS THEME (THE ULTIMATE FIX) ---
st.markdown("""
<style>
    /* Primary Colors & Background */
    .stApp {
        background-color: #F9FAFB;
        color: #1F2937;
    }
    
    /* Input Boxes Background */
    .stTextInput>div>div>input, .stTextArea>div>div>textarea, .stNumberInput>div>div>input {
        background-color: #FFFFFF;
        color: #1F2937;
    }
    
    /* Button Styling (The Blue Premium Look) */
    .stButton>button {
        background-color: #4F46E5 !important;
        color: white !important;
        border-radius: 8px;
        border: none;
        padding: 10px 24px;
        font-weight: bold;
    }
    
    /* Button Hover Effect */
    .stButton>button:hover {
        background-color: #4338CA !important;
        color: white !important;
        border-color: #4338CA !important;
    }
    
    /* Headers & Titles */
    h1, h2, h3, h4, h5, h6 {
        color: #1F2937;
    }
    
    /* AI Score Metric Color */
    [data-testid="stMetricValue"] {
        color: #4F46E5;
        font-weight: 800;
    }
</style>
""", unsafe_allow_html=True)

# --- CUSTOM HEADER WITH LOGO ---
header_col1, header_col2 = st.columns([1, 4]) 

with header_col1:
    # Namma logo.png file irundha kaattum, illana placeholder kaattum
    if os.path.exists("logo.png"):
        st.image("logo.png", width=180)
    else:
        st.write("🏢 **[Company Logo]**") 

with header_col2:
    st.title("N2S Perfect Matching Resume Screening")
    st.markdown("##### *Smart Filtering & Semantic Ranking Engine*")

st.divider()

# --- SEARCH DASHBOARD ---
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    jd_input = st.text_area("📋 Job Description / Key Skills:", height=100)
with col2:
    min_exp = st.number_input("⏳ Min Experience:", min_value=0, value=10)
with col3:
    target_loc_input = st.text_input("📍 Location:", value="USA")

if st.button("🚀 Find Perfect Matches"):
    if jd_input and target_loc_input:
        try:
            with st.spinner("Applying 4 Strict Rules (Exp, Loc, Role, Core Skill)..."):
                rules = perfect_match_rules(jd_input, target_loc_input)
                all_states = [rules['state_code']] + rules['nearby']
                state_str = "','".join(all_states)
                
                role_conditions = " OR ".join([f"role LIKE '%{keyword}%'" for keyword in rules['role_keywords']])
                mandatory_skill = rules['mandatory_skill']
                
                db = get_db_connection()
                sql_query = f"""
                    SELECT * FROM candidates 
                    WHERE experience >= {min_exp} 
                    AND location IN ('{state_str}')
                    AND ({role_conditions})
                    AND resume_text LIKE '%{mandatory_skill}%'
                """
                df = pd.read_sql(sql_query, db)
                db.close()

                if not df.empty:
                    jd_embedding = ranking_model.encode(jd_input, convert_to_tensor=True)
                    resume_embeddings = ranking_model.encode(df['resume_text'].tolist(), convert_to_tensor=True)
                    
                    scores = util.cos_sim(jd_embedding, resume_embeddings)[0]
                    raw_scores = scores.tolist()
                    
                    # ATS Score Booster
                    adjusted_scores = [min(99.2, 75 + (s * 40)) for s in raw_scores]
                    df['AI_Score'] = [round(s, 1) for s in adjusted_scores]
                    
                    final_results = df.sort_values(by='AI_Score', ascending=False).drop_duplicates(subset=['name']).head(5)

                    st.success(f"Passed Strict Rules! Mandatory Skill: '{mandatory_skill}'. Valid Roles: {rules['role_keywords']}. Showing Top Matches:")
                    
                    for _, row in final_results.iterrows():
                        display_candidate(row)
                else:
                    st.warning(f"No candidates passed ALL 4 strict rules (Exp: {min_exp}+, Loc: {all_states}, Roles: {rules['role_keywords']}, Skill: {mandatory_skill}).")
        
        except Exception as e:
            st.error(f"Error: {e}")
    else:
        st.error("Please enter JD and Location!")