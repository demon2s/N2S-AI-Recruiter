import streamlit as st
import mysql.connector
import pandas as pd
import os
import json
import warnings
from openai import OpenAI
from sentence_transformers import SentenceTransformer, util
from dotenv import load_dotenv # PUDHUSA ADD PANNADHU

# --- Setup ---
warnings.filterwarnings('ignore')
os.environ['TOKENIZERS_PARALLELISM'] = 'false'

# .env file-la irukka passwords-ah Python-kulla load panrom
load_dotenv() 

# Ippo AI key automatic-ah ulla vandhudum
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

# --- MAIN UI ---
st.set_page_config(page_title="Perfect Match AI", layout="wide")
st.title("🎯N2S Perfect Match AI Screener")

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