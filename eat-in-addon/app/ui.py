import streamlit as st
import os
import base64
import json
import uuid
from datetime import datetime
from PIL import Image
from main import SessionLocal, Recipe, Ingredient, Instruction, Tag, RecipeImage, init_db
from sqlalchemy.orm import Session
import requests
import urllib3
from html import escape

# נטרול אזהרות SSL לא נחוצות כאשר עוקפים את אימות התעודות של אתרים מקומיים
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Initializing database
init_db()

# נשאיר את המשתנה ריק כדי שהמערכת תתבסס על ההזנה הישירה והבטוחה שלך בהגדרות
apiKey = "" 

# פונקציה חכמה למציאת מפתח ה-API הפעיל
def get_effective_api_key():
    # 1. אם המשתמש שמר את המפתח בתוך הגדרות האפליקציה (עדיפות ראשונה)
    if "app_api_key" in st.session_state and st.session_state.app_api_key.strip():
        return st.session_state.app_api_key.strip()
        
    # 2. בדיקה של המשתנה המקומי בקוד
    clean_key = apiKey.strip() if apiKey else ""
    if clean_key and "הדבק" not in clean_key and len(clean_key) > 10:
        return clean_key
        
    # 3. בדיקת משתנה הסביבה של המערכת
    env_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if env_key and len(env_key) > 10:
        return env_key
        
    # 4. בדיקת קובץ ההגדרות של Home Assistant
    try:
        with open('/data/options.json') as f:
            ha_key = json.load(f).get('gemini_api_key', '').strip()
            if ha_key and len(ha_key) > 10:
                return ha_key
    except:
        pass
    return ""

# פונקציה יצירתית לביצוע פנייה ישירה ל-API של גוגל באמצעות REST הכוללת Fallback חכם ונטרול אימות SSL מקומי
def generate_recipe_via_rest_api(active_key, prompt_text, image_b64=None, mime_type=None):
    headers = {
        "Content-Type": "application/json"
    }
    
    # בניית גוף הבקשה (Payload) והגדרת רשימת המודלים לגיבוי
    if image_b64 and mime_type:
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt_text},
                    {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": image_b64
                        }
                    }
                ]
            }]
        }
        models_to_try = [
            'gemini-2.5-flash',
            'gemini-1.5-flash', 
            'gemini-1.5-flash-latest', 
            'gemini-1.5-pro', 
            'gemini-1.5-pro-latest'
        ]
    else:
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt_text}
                ]
            }]
        }
        models_to_try = [
            'gemini-2.5-flash',
            'gemini-1.5-flash', 
            'gemini-1.5-flash-latest', 
            'gemini-1.5-pro', 
            'gemini-1.5-pro-latest'
        ]
        
    last_error = None
    
    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={active_key}"
        
        try:
            # הוספת verify=False כדי לעקוף את בעיות תעודת ה-SSL המקומיות בהצלחה
            response = requests.post(url, json=payload, headers=headers, timeout=30, verify=False)
            
            if response.status_code == 200:
                result_json = response.json()
                try:
                    return result_json['candidates'][0]['content']['parts'][0]['text']
                except KeyError:
                    last_error = Exception(f"המבנה שחזר מהמודל {model} לא תקין.")
                    continue
            else:
                try:
                    error_details = response.json().get('error', {}).get('message', 'שגיאה לא ידועה')
                except:
                    error_details = response.text
                
                if response.status_code == 404 or "not found" in error_details.lower() or "not_found" in error_details.lower():
                    last_error = Exception(f"המודל {model} החזיר שגיאה 404 (לא נמצא במערכת), מנסה לעבור למודל הבא...")
                    continue
                elif response.status_code in [400, 403]:
                    raise Exception(f"שגיאת אימות מול גוגל ({response.status_code}): אנא ודא שמפתח ה-API שהוזן תקין ופעיל. פרטים: {error_details}")
                else:
                    last_error = Exception(f"שגיאה {response.status_code} במודל {model}: {error_details}")
                    continue
                    
        except Exception as e:
            last_error = e
            if "שגיאת אימות" in str(e):
                raise e
            continue
            
    raise Exception(f"כל הניסיונות למצוא מודל נתמך נכשלו. ודא שמפתח ה-API שהוזן אכן פעיל. שגיאה אחרונה: {str(last_error)}")

UPLOAD_DIR = "uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

st.set_page_config(
    page_title="Eat-In | ניהול מתכונים חכם",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Advanced CSS for RTL, Grid UI, Settings Button and Responsive Layouts ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Assistant:wght@300;400;600;700;800&display=swap');
    
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        direction: rtl;
        text-align: right;
        font-family: 'Assistant', sans-serif;
        background-color: #f8fafc;
    }

    /* Hide Streamlit's auto-generated link/anchor icons globally */
    .anchor-link, [data-testid="stHeader"] a, h1 a, h2 a, h3 a, .stMarkdown svg {
        display: none !important;
        visibility: hidden !important;
    }

    /* Increase padding to prevent header overlap on action buttons */
    .block-container {
        padding-top: 5.5rem !important;
        padding-bottom: 2rem !important;
    }

    /* Force RTL on all text containers */
    div[data-testid="stMarkdownContainer"], div[data-testid="stText"] {
        text-align: right !important;
        direction: rtl !important;
    }

    /* Title Styling */
    .centered-title { 
        text-align: center; 
        color: #1e293b; 
        margin: 1.2rem 0; 
        font-weight: 800; 
        font-size: 2.8rem; 
    }

    /* --- סידור עמודות כרטיסי המתכונים בגריד מרובע רספונסיבי ללא חפיפות --- */
    /* ===== Recipe Grid ===== */

    .recipe-grid {
        margin-top: 30px;
    }

    .recipe-card {
        position: relative;
        border-radius: 22px;
        overflow: hidden;
        height: 320px;
        cursor: pointer;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        box-shadow: 0 6px 18px rgba(0,0,0,0.08);
        margin-bottom: 25px;
        background: #e2e8f0;
    }

    .recipe-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 24px rgba(0,0,0,0.12);
    }

    .recipe-card img {
        width: 100%;
        height: 100%;
        object-fit: cover;
    }

    .recipe-title-overlay {
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;

        background: rgba(255,255,255,0.70);
        backdrop-filter: blur(6px);

        padding: 16px 14px;

        text-align: center;
        font-size: 1.05rem;
        font-weight: 800;
        color: #1e293b;

        z-index: 2;
    }

    .recipe-card-button button {
        position: absolute !important;
        inset: 0 !important;

        width: 100% !important;
        height: 100% !important;

        opacity: 0 !important;
        border: none !important;
        background: transparent !important;

        z-index: 5 !important;
        cursor: pointer !important;
    }

    /* ביטול עיצובי column גלובליים שגרמו לבאג האנכי */
    div[data-testid="column"] {
        margin-bottom: 0 !important;
    }

    /* עיצוב התמונות בתוך כרטיסי הגלריה - פינות מעוגלות עליונות בגודל מוקטן ומהודק */
    div[data-testid="column"] [data-testid="stImage"] img {
        border-radius: 12px 12px 0 0 !important;
        height: 150px !important; /* Slightly smaller height */
        object-fit: cover !important;
        width: 100% !important;
        border: 1px solid #e2e8f0 !important;
        border-bottom: none !important;
        box-shadow: 0 4px 10px rgba(0,0,0,0.03) !important;
    }

    /* עיצוב כפתור שם המתכון שיושב בדיוק כפוטר לבן צמוד לתמונה - מוקטן */
    div[data-testid="column"] .stButton > button {
        width: 100% !important;
        height: 48px !important; /* Slightly smaller height */
        border-radius: 0 0 12px 12px !important; /* מעוגל בתחתית בלבד */
        border: 1px solid #e2e8f0 !important;
        border-top: 1px solid #f1f5f9 !important;
        background-color: #ffffff !important;
        color: #1e293b !important;
        font-weight: 700 !important;
        font-size: 0.95rem !important; /* Slightly smaller text */
        text-align: center !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05) !important;
        margin-top: -1px !important; /* הצמדה מלאה לתמונה מעל */
        transition: all 0.2s ease !important;
    }

    div[data-testid="column"] .stButton > button:hover {
        background-color: #f8fafc !important;
        color: #3b82f6 !important;
        border-color: #cbd5e1 !important;
        transform: translateY(1px) !important;
    }

    /* כותרות מקטעים בתוך טפסים */
    .section-title {
        color: #1e293b; font-weight: 800; margin-bottom: 20px;
        border-right: 5px solid #3b82f6; padding-right: 15px; font-size: 1.6rem;
        text-align: right; display: block;
    }

    /* Hero Section for Recipe Page */
    .recipe-hero-container {
        width: 100%; height: 400px; position: relative; border-radius: 24px;
        overflow: hidden; margin-bottom: 2rem; background-position: center;
        background-repeat: no-repeat; background-size: cover;
    }
    .hero-overlay {
        position: absolute; bottom: 0; right: 0; left: 0; top: 0;
        background: linear-gradient(to top, rgba(0,0,0,0.8) 0%, transparent 100%);
        display: flex; flex-direction: column; justify-content: flex-end;
        padding: 40px; color: white; text-align: right;
    }

    .ingredient-line {
        margin-bottom: 10px; direction: rtl; text-align: right; font-size: 1.1rem; color: #334155;
    }
    
    .step-item {
        display: flex; gap: 15px; margin-bottom: 12px; padding: 12px;
        background: #f8fafc; border-radius: 14px; direction: rtl; align-items: flex-start;
    }
    .step-number {
        background: #3b82f6; color: white; min-width: 28px; max-width: 28px; height: 28px;
        border-radius: 50%; display: flex; align-items: center; justify-content: center;
        font-weight: 700; font-size: 0.85rem; flex-shrink: 0; margin-top: 2px;
    }

    /* --- עיצוב קונטיינרים מעוצבים לטפסים - מותאם למחשב ולמובייל --- */
    div[data-testid*="VerticalBlock"]:has(#general-info-anchor),
    div[class*="VerticalBlock"]:has(#general-info-anchor),
    div[data-testid*="VerticalBlock"]:has(#ingredients-container-anchor),
    div[class*="VerticalBlock"]:has(#ingredients-container-anchor),
    div[data-testid*="VerticalBlock"]:has(#steps-container-anchor),
    div[class*="VerticalBlock"]:has(#steps-container-anchor),
    div[data-testid*="VerticalBlock"]:has(#image-container-anchor),
    div[class*="VerticalBlock"]:has(#image-container-anchor) {
        width: 100% !important;
        max-width: 1100px !important; 
        min-width: 320px !important;
        margin: 0 auto 25px auto !important;
        background: white !important;
        border-radius: 20px !important;
        padding: 25px !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05) !important;
        border: 1px solid #f1f5f9 !important;
    }

    /* 🗑️ פתרון אנכי מושלם לפח של שלבי ההכנה והמצרכים (מול שדה הטקסט וה-TextArea) */
    div[data-testid="column"]:has(#step-delete-container-inner),
    div[class*="column"]:has(#step-delete-container-inner) {
        align-self: center !important;
        margin-top: 15px !important;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
    }
    div[data-testid="column"]:has(#step-delete-container-inner) div[data-testid="stWidgetLabelSpacer"],
    div[class*="column"]:has(#step-delete-container-inner) div[data-testid="stWidgetLabelSpacer"] {
        display: none !important;
    }
    
    div[data-testid="column"]:has(#ing-delete-container-inner),
    div[class*="column"]:has(#ing-delete-container-inner) {
        align-self: center !important;
        margin-top: 15px !important;
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
    }
    div[data-testid="column"]:has(#ing-delete-container-inner) div[data-testid="stWidgetLabelSpacer"],
    div[class*="column"]:has(#ing-delete-container-inner) div[data-testid="stWidgetLabelSpacer"] {
        display: none !important;
    }

    /* Align nested buttons of delete column globally to prevent padding mismatch */
    div[data-testid="column"]:has(#step-delete-container-inner) .stButton,
    div[data-testid="column"]:has(#ing-delete-container-inner) .stButton {
        margin-top: 0 !important;
        margin-bottom: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }

    div[data-testid*="VerticalBlock"]:has(#import-container-anchor),
    div[class*="VerticalBlock"]:has(#import-container-anchor) {
        width: 100% !important;
        max-width: 650px !important;
        min-width: 320px !important;
        margin: 0 auto 25px auto !important;
        background: white !important;
        border-radius: 20px !important;
        padding: 25px !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05) !important;
        border: 1px solid #f1f5f9 !important;
    }

    div[data-testid*="VerticalBlock"]:has(#actions-container-anchor),
    div[class*="VerticalBlock"]:has(#actions-container-anchor) {
        width: 100% !important;
        max-width: 1100px !important;
        min-width: 320px !important;
        margin: 0 auto 25px auto !important;
    }

    /* כפתורים סטנדרטיים ברחבי המערכת */
    div[data-testid*="column"]:not(:has([id^="recipe-anchor-"])) .stButton > button,
    div[class*="Column"]:not(:has([id^="recipe-anchor-"])) .stButton > button {
        width: 100% !important;
        height: 42px !important;
        border-radius: 12px !important;
        border: 1px solid #cbd5e1 !important;
        background-color: #ffffff !important;
        color: #1e293b !important;
        font-weight: 700 !important;
        font-size: 0.95rem !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
        transition: all 0.2s ease !important;
    }

    div[data-testid*="column"]:not(:has([id^="recipe-anchor-"])) .stButton > button:hover,
    div[class*="Column"]:not(:has([id^="recipe-anchor-"])) .stButton > button:hover {
        border-color: #3b82f6 !important;
        color: #3b82f6 !important;
        background-color: #f8fafc !important;
    }

    /* --- יישור כפתורי חזרה ועריכה בדף צפייה --- */
    div[data-testid="column"]:has(#view-back-container) {
        display: flex !important;
        justify-content: flex-start !important;
    }
    div[data-testid="column"]:has(#view-edit-container) {
        display: flex !important;
        justify-content: flex-end !important;
    }
</style>
""", unsafe_allow_html=True)

# Navigation and State management
if 'page' not in st.session_state: st.session_state.page = 'library'
if 'selected_id' not in st.session_state: st.session_state.selected_id = None
if 'form_initialized' not in st.session_state: st.session_state.form_initialized = None
if 'user_api_key' not in st.session_state: st.session_state.user_api_key = ""
if 'app_api_key' not in st.session_state: st.session_state.app_api_key = ""

# ניהול מזהי גרסאות לווידג'טים דינמיים למניעת באגי זיכרון של Streamlit
if 'steps_version' not in st.session_state: st.session_state.steps_version = 0
if 'ings_version' not in st.session_state: st.session_state.ings_version = 0

# Load API key initially if exists in Home Home Assistant config
if not st.session_state.app_api_key:
    try:
        with open('/data/options.json') as f:
            st.session_state.app_api_key = json.load(f).get('gemini_api_key', '').strip()
    except:
        pass

def navigate(page, id=None):

    st.session_state.page = page

    if id:
        st.session_state.selected_id = id

    # ===== Sync URL =====
    try:

        if page == "view" and id:
            st.query_params["page"] = "view"
            st.query_params["recipe_id"] = str(id)

        else:
            st.query_params.clear()

    except:

        if page == "view" and id:
            st.experimental_set_query_params(
                page="view",
                recipe_id=id
            )
        else:
            st.experimental_set_query_params()
def sync_page_from_query_params():
    try:
        page = st.query_params.get("page")
        recipe_id = st.query_params.get("recipe_id")
    except:
        qp = st.experimental_get_query_params()
        page = qp.get("page", [None])[0]
        recipe_id = qp.get("recipe_id", [None])[0]

    if page == "view" and recipe_id:
        try:
            st.session_state.page = "view"
            st.session_state.selected_id = int(recipe_id)
        except:
            pass

sync_page_from_query_params()

sync_page_from_query_params()
# --- שורת ניווט עליונה גלובלית (מונעת באגי מיקום או אי-לחיצות של כפתורים מחוץ ל-DOM) ---
header_right, header_mid, header_left = st.columns([2, 4, 4])

with header_right:
    # לוגו עליון עדין
    st.markdown('<div style="font-weight: 800; font-size: 1.8rem; color: #1e293b; margin-top: 5px; cursor: pointer;">Eat-In 🍽️</div>', unsafe_allow_html=True)

with header_mid:
    st.write("") # מרווח אמצעי

with header_left:
    # כפתורי פעולה עליונים מיושרים לשמאל, באותו גובה בדיוק, ללא חפיפות
    btn_col_settings, btn_col_add = st.columns(2)
    with btn_col_add:
        if st.session_state.page == 'library':
            if st.button("➕ הוספת מתכון", key="global_add_recipe_btn", type="primary", use_container_width=True):
                navigate('select_method')
                st.rerun()
    with btn_col_settings:
        if st.button("⚙️ הגדרות", key="global_settings_btn", use_container_width=True):
            navigate('settings')
            st.rerun()


# --- Settings Page ---
if st.session_state.page == 'settings':
    with st.container():
        st.markdown('<div id="import-container-anchor"></div>', unsafe_allow_html=True)
        st.markdown('<h2 style="text-align:right; margin-bottom:1.5rem;">⚙️ הגדרות מערכת</h2>', unsafe_allow_html=True)
        st.write("כאן תוכל להגדיר את מפתח ה-API שלך באופן קבוע, ללא צורך בהזנתו מחדש בכל ייבוא.")
        
        saved_key = st.session_state.app_api_key if st.session_state.app_api_key else ""
        new_key = st.text_input(
            "מפתח ה-API שלך מ-Google AI Studio:", 
            value=saved_key, 
            type="password",
            placeholder="הדבק כאן את מפתח ה-API הסודי שלך"
        )
        st.caption("המפתח נשמר בזיכרון האפליקציה ומשמש אוטומטית לכל סריקות ה-AI במערכת.")
        
        st.divider()
        c_save, c_back = st.columns([1, 1])
        if c_save.button("💾 שמור הגדרות", type="primary", use_container_width=True):
            st.session_state.app_api_key = new_key.strip()
            st.success("ההגדרות נשמרו בהצלחה!")
            navigate('library')
            st.rerun()
            
        if c_back.button("חזרה לספרייה", use_container_width=True):
            navigate('library')
            st.rerun()

# --- Library Page ---
# --- Library Page ---
elif st.session_state.page == 'library':

    st.markdown("""
    <style>
        .eatin-title {
            text-align: center;
            font-size: 4rem;
            font-weight: 900;
            margin-top: 10px;
            margin-bottom: 8px;
            background: linear-gradient(90deg, #0f172a, #334155);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -2px;
        }

        .eatin-subtitle {
            text-align: center;
            color: #64748b;
            margin-bottom: 30px;
            font-size: 1rem;
        }

        .recipe-grid {
            margin-top: 20px;
        }

        .recipe-card-link {
            text-decoration: none !important;
            display: block;
        }

        .recipe-card {
            position: relative;
            border-radius: 24px;
            overflow: hidden;
            height: 320px;
            margin-bottom: 25px;
            box-shadow: 0 8px 22px rgba(0,0,0,0.08);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
            background: #e5e7eb;
        }

        .recipe-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 14px 28px rgba(0,0,0,0.12);
        }

        .recipe-card img {
            width: 100%;
            height: 100%;
            object-fit: cover;
            display: block;
        }

        .recipe-title-overlay {
            position: absolute;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(255,255,255,0.70);
            backdrop-filter: blur(6px);
            padding: 16px;
            text-align: center;
            font-size: 1.05rem;
            font-weight: 800;
            color: #0f172a;
            z-index: 2;
        }

        div[data-testid="column"] {
            margin-bottom: 0 !important;
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="eatin-title">Eat-In</div>
    <div class="eatin-subtitle">ספריית המתכונים החכמה שלך</div>
    """, unsafe_allow_html=True)

    _, search_col, _ = st.columns([1.5, 2.5, 1.5])

    with search_col:
        query = st.text_input(
            "",
            placeholder="🔍 חפש מתכון...",
            label_visibility="collapsed"
        )

    db = SessionLocal()

    recipes = (
        db.query(Recipe).filter(Recipe.name.contains(query)).all()
        if query
        else db.query(Recipe).all()
    )

    def to_image_src(image_path):
        if image_path and os.path.exists(image_path):
            ext = os.path.splitext(image_path)[1].lower()
            if ext in [".png"]:
                mime = "image/png"
            elif ext in [".webp"]:
                mime = "image/webp"
            else:
                mime = "image/jpeg"
            with open(image_path, "rb") as f:
                return f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"
        if image_path and str(image_path).startswith("http"):
            return image_path
        return "https://images.unsplash.com/photo-1495521821757-a1efb6729352?w=900"

    if not recipes:
        st.info("אין מתכונים בספרייה.")
    else:
        st.markdown('<div class="recipe-grid">', unsafe_allow_html=True)

        recipe_chunks = [recipes[i:i + 4] for i in range(0, len(recipes), 4)]

        for chunk in recipe_chunks:
            cols = st.columns(4)

            for idx, r in enumerate(chunk):
                with cols[idx]:
                    img_path = r.images[-1].image_path if r.images else None
                    image_src = to_image_src(img_path)
                    recipe_name = escape(r.name or "")

                    st.markdown(
                        f"""
                        <a class="recipe-card-link" href="?page=view&recipe_id={r.id}" target="_self">
                            <div class="recipe-card">
                                <img src="{image_src}" alt="{recipe_name}">
                                <div class="recipe-title-overlay">{recipe_name}</div>
                            </div>
                        </a>
                        """,
                        unsafe_allow_html=True
                    )

        st.markdown('</div>', unsafe_allow_html=True)

    db.close()

# --- Select Creation Method Page ---
elif st.session_state.page == 'select_method':

    # יצירת מרווח עליון ומרכוז
    _, center_box, _ = st.columns([1, 1.5, 1])

    with center_box:
        st.markdown('<div id="select-method-anchor"></div>', unsafe_allow_html=True)
        
        # כותרת מרשימה
        st.markdown('''
            <div style="text-align: center; margin-bottom: 20px;">
                <span style="font-size: 3.5rem;">✨</span>
                <h2 style="color: #1e293b; font-weight: 800; font-size: 2.4rem; margin-top: 10px; margin-bottom: 5px;">הוספת מתכון חדש</h2>
                <p style="color: #64748b; font-size: 1.1rem;">בחר את הדרך הנוחה ביותר עבורך</p>
            </div>
        ''', unsafe_allow_html=True)

        # יצירת התיבה
        st.markdown('<div>',unsafe_allow_html=True)
        
        # כפתורים בעלי רוחב מלא בתוך התיבה (התיבה עצמה מוגבלת ל-350px)
        # 1. מגדירים עמודות כדי למרכז ולצמצם את הרוחב של הכפתורים
        # הפיכת ה-1.8 למספר גדול יותר תהפוך את הכפתורים לצרים יותר (למשל [1.5, 1.0, 1.5] יהיה צר מאוד)
        _, btn_container, _ = st.columns([1.5, 1.4, 1.5])

        with btn_container:
            # 2. הכפתורים עם הגדרת use_container_width=True כדי שיתאימו בדיוק לרוחב העמודה שבחרת
            if st.button("📝 מתכון ידני", use_container_width=True, type="primary"):
                st.session_state.form_initialized = None
                navigate('form')
                st.rerun()

            if st.button("📸 מתוך תמונה", use_container_width=True):
                navigate('import_image')
                st.rerun()

            if st.button("🌐 מתוך אתר אינטרנט", use_container_width=True):
                navigate('import_url')
                st.rerun()

            st.divider()

            if st.button("❌ ביטול", use_container_width=True):
                navigate('library')
                st.rerun()

        # סגירת התיבה
        st.markdown('</div>', unsafe_allow_html=True)

# --- Import URL Page (AI Scraper with REST API) ---
elif st.session_state.page == 'import_url':

    with st.container():

        st.markdown("""
        <style>

        .import-url-container {

            max-width: 650px !important;
            margin: 0 auto !important;

            background: white;

            border-radius: 28px;

            padding: 35px;

            border: 1px solid #e2e8f0;

            box-shadow: 0 10px 35px rgba(0,0,0,0.06);
        }

        .import-url-title {

            text-align: right;

            font-size: 2rem;
            font-weight: 800;

            color: #0f172a;

            margin-bottom: 10px;
        }

        .import-url-subtitle {

            text-align: right;

            color: #64748b;

            margin-bottom: 24px;

            line-height: 1.6;
        }

        .import-url-container .stButton button {

            height: 56px !important;

            border-radius: 18px !important;

            font-size: 1rem !important;
            font-weight: 700 !important;

            transition: all 0.2s ease !important;
        }

        .import-url-container .stButton button:hover {

            transform: translateY(-2px) !important;
        }

        </style>
        """, unsafe_allow_html=True)

        st.markdown(
            """
            <div class="import-url-container">
                <div class="import-url-title">
                    🌐 ייבוא מתכון מאתר אינטרנט באמצעות AI
                </div>
                <div class="import-url-subtitle">
                    הדבק קישור למתכון והמערכת תנתח אותו אוטומטית באמצעות Gemini AI
                </div>
            </div>
            """,
            unsafe_allow_html=True
)
        st.markdown('<div class="import-url-wrapper"></div>', unsafe_allow_html=True)
        active_key = get_effective_api_key()

        if active_key:
            st.success("🔑 מפתח Gemini API מוגדר ופעיל במערכת")
        else:
            st.error(
                "⚠️ לא מוגדר מפתח Gemini API! אנא כנס להגדרות API והגדר מפתח פעיל."
            )

        url_input = st.text_input(
            "הדבק את כתובת האתר (URL) של המתכון:",
            placeholder="https://www.mako.co.il/food-recipes/..."
        )

        st.caption(
            "ה-AI ינתח את כל המאמר, יחלץ את המצרכים וההוראות ויעביר אותך לטופס העריכה לפני השמירה."
        )

        st.divider()

        _, c_btn1, c_btn2, _ = st.columns([2, 1, 1, 2])

        with c_btn1:

            analyze_clicked = st.button(
                "🔍 נתח את האתר",
                key="url_analyze",
                type="primary",
                use_container_width=True,
                disabled=(not active_key or not url_input)
            )

        with c_btn2:

            back_clicked = st.button(
                "❌ ביטול",
                use_container_width=True
            )

        st.markdown("</div>", unsafe_allow_html=True)

    # ===== חזרה =====
    if back_clicked:
        navigate('select_method')
        st.rerun()

    # ===== ניתוח אתר =====
    if analyze_clicked and url_input:

        with st.spinner("ה-AI קורא ומפענח את האתר (Gemini 1.5/2.5)..."):

            try:

                import requests
                from bs4 import BeautifulSoup

                headers = {
                    'User-Agent': (
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                        'AppleWebKit/537.36 (KHTML, like Gecko) '
                        'Chrome/120.0 Safari/537.36'
                    )
                }

                response = requests.get(
                    url_input,
                    headers=headers,
                    timeout=15,
                    verify=False
                )

                soup = BeautifulSoup(response.text, 'html.parser')

                raw_text = soup.get_text(separator=' ')
                clean_text = " ".join(raw_text.split())[:10000]

                prompt = """
Analyze this recipe webpage text and extract the structured recipe data.

Return ONLY a valid JSON object matching this structure EXACTLY.

{
  "name": "Recipe Name in Hebrew",
  "prep_time": "Preparation time in Hebrew",
  "servings": "Number of servings",
  "ingredients": [
    {
      "amount": "quantity",
      "unit": "unit",
      "name": "ingredient name"
    }
  ],
  "steps": [
    {
      "section": "section title",
      "text": "step description"
    }
  ]
}

Important Rules:

1. Translate everything to fluent Hebrew.
2. Do NOT write step numbers.
3. Return valid JSON only.
"""

                response_text = generate_recipe_via_rest_api(
                    active_key,
                    f"{prompt}\nWebpage Content:\n{clean_text}"
                )

                raw_json = (
                    response_text
                    .replace('```json', '')
                    .replace('```', '')
                    .strip()
                )

                recipe_data = json.loads(raw_json)

                # ===== בסיס =====
                st.session_state.f_name = recipe_data.get("name", "")
                st.session_state.f_prep = recipe_data.get("prep_time", "")
                st.session_state.f_serv = recipe_data.get("servings", "")

                # ===== רכיבים =====
                st.session_state.f_ings = []

                for ing in recipe_data.get("ingredients", []):

                    st.session_state.f_ings.append({
                        "name": ing.get("name", ""),
                        "amount": ing.get("amount", ""),
                        "unit": ing.get("unit", "")
                    })

                if not st.session_state.f_ings:

                    st.session_state.f_ings = [{
                        "name": "",
                        "amount": "",
                        "unit": ""
                    }]

                # ===== שלבים =====
                st.session_state.f_steps = []

                for step in recipe_data.get("steps", []):

                    st.session_state.f_steps.append({
                        "section": (
                            step.get("section", "")
                            if step.get("section", "") != "כללי"
                            else ""
                        ),
                        "text": step.get("text", "")
                    })

                if not st.session_state.f_steps:

                    st.session_state.f_steps = [{
                        "section": "",
                        "text": ""
                    }]

                # ===== מעבר לטופס =====
                st.session_state.form_initialized = "scraped_recipe_data"

                navigate('form')

                st.rerun()

            except Exception as e:

                st.error(
                    f"אירעה שגיאה בניתוח המתכון מהאתר: {e}"
                )

# --- Import Image Page (AI Vision with REST API Support) ---
elif st.session_state.page == 'import_image':
    with st.container():
        st.markdown('<div id="import-container-anchor"></div>', unsafe_allow_html=True)
        st.markdown('<h2 style="text-align:right; margin-bottom:1.5rem;">📸 סריקת מתכון מתמונה / צילום באמצעות AI</h2>', unsafe_allow_html=True)
        
        active_key = get_effective_api_key()
        
        if active_key:
            st.success("🔑 מפתח Gemini API מוגדר ופעיל במערכת")
        else:
            st.error("⚠️ לא מוגדר מפתח Gemini API! אנא כנס להגדרות API בסרגל הצד השמאלי והגדר מפתח פעיל כדי להשתמש ב-AI.")
            
        uploaded_file = st.file_uploader("העלה צילום מסך, דף מספר בישול או תמונה של מתכון:", type=['png', 'jpg', 'jpeg'])
        st.caption("ה-AI יפענח את הטקסט ישירות מהתמונה, יסדר אותו ויעביר אותך לטופס העריכה.")
        
        st.divider()
        c_btn1, c_btn2 = st.columns([1, 1])
        analyze_clicked = c_btn1.button("🔍 נתח את התמונה", key="img_analyze", type="primary", use_container_width=True, disabled=(not active_key or uploaded_file is None))
        back_clicked = c_btn2.button("ביטול", use_container_width=True)

    if back_clicked:
        navigate('select_method')
        st.rerun()

    if analyze_clicked and uploaded_file is not None:
        with st.spinner("ה-AI קורא ומפענח את התמונה (Gemini 1.5/2.5)..."):
            try:
                import io
                img = Image.open(uploaded_file)
                
                buffered = io.BytesIO()
                img.convert("RGB").save(buffered, format="JPEG", quality=80)
                img_b64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
                
                prompt = """
                Analyze this recipe image and extract all structured details.
                Return ONLY a valid JSON object matching this structure EXACTLY, with no markdown code blocks (do not wrap in ```json):
                {
                  "name": "Recipe Name in Hebrew",
                  "prep_time": "Preparation time in Hebrew (e.g. 'שעה וחצי')",
                  "servings": "Number of servings (e.g. '5')",
                  "ingredients": [
                    {"amount": "quantity or decimal (e.g. '1', '250', 'חצי')", "unit": "unit of measure (e.g. 'כפית', 'גרם', 'כוס')", "name": "ingredient name (e.g. 'מלח')"}
                  ],
                  "steps": [
                    {"section": "part title (e.g. 'למילוי' or 'כללי' if none)", "text": "step description"}
                  ]
                }
                Important Rules:
                1. Translate everything to fluent Hebrew.
                2. Do NOT write step numbers in the 'text' fields (e.g. write 'מחממים תנור ל-180 מעלות' instead of '1. מחממים תנור').
                3. Ensure the JSON is valid and contains no markup wrappers.
                """
                
                response_text = generate_recipe_via_rest_api(active_key, prompt, img_b64, "image/jpeg")
                
                raw_json = response_text.replace('```json', '').replace('```', '').strip()
                recipe_data = json.loads(raw_json)
                
                st.session_state.f_name = recipe_data.get("name", "")
                st.session_state.f_prep = recipe_data.get("prep_time", "")
                st.session_state.f_serv = recipe_data.get("servings", "")
                
                st.session_state.f_ings = []
                for ing in recipe_data.get("ingredients", []):
                    st.session_state.f_ings.append({
                        "name": ing.get("name", ""),
                        "amount": ing.get("amount", ""),
                        "unit": ing.get("unit", "")
                    })
                if not st.session_state.f_ings:
                    st.session_state.f_ings = [{"name": "", "amount": "", "unit": ""}]
                
                st.session_state.f_steps = []
                for step in recipe_data.get("steps", []):
                    st.session_state.f_steps.append({
                        "section": step.get("section", "") if step.get("section", "") != "כללי" else "",
                        "text": step.get("text", "")
                    })
                if not st.session_state.f_steps:
                    st.session_state.f_steps = [{"section": "", "text": ""}]
                
                st.session_state.form_initialized = "scraped_recipe_data"
                uploaded_file = None
                navigate('form')
                st.rerun()
                
            except Exception as e:
                st.error(f"אירעה שגיאה בפענוח המתכון מהתמונה: {e}")

# --- Form/Edit Page ---
elif st.session_state.page in ['form', 'edit']:
    is_edit = st.session_state.page == 'edit'
    db = SessionLocal()
    
    if st.session_state.form_initialized == "scraped_recipe_data":
        st.session_state.form_initialized = (st.session_state.selected_id if is_edit else "new")
    elif st.session_state.form_initialized != (st.session_state.selected_id if is_edit else "new"):
        if is_edit:
            recipe = db.query(Recipe).get(st.session_state.selected_id)
            st.session_state.f_name = recipe.name
            st.session_state.f_prep = recipe.prep_time
            st.session_state.f_serv = recipe.servings
            
            st.session_state.f_ings = []
            for ing in recipe.ingredients:
                parts = [p.strip() for p in ing.name.split('|')]
                if len(parts) >= 3:
                    st.session_state.f_ings.append({"name": parts[2], "amount": parts[0], "unit": parts[1]})
                else:
                    st.session_state.f_ings.append({"name": ing.name, "amount": "", "unit": ""})
            
            st.session_state.f_steps = []
            for inst in recipe.instructions:
                st.session_state.f_steps.append({"section": inst.section if inst.section != "כללי" else "", "text": inst.text})
        else:
            st.session_state.f_name, st.session_state.f_prep, st.session_state.f_serv = "", "", ""
            st.session_state.f_ings = [{"name": "", "amount": "", "unit": ""}]
            st.session_state.f_steps = [{"section": "", "text": ""}]
        st.session_state.form_initialized = st.session_state.selected_id if is_edit else "new"

    st.markdown('<div class="form-container">', unsafe_allow_html=True)
    st.markdown(f'<h2 style="text-align:right; font-weight:800; margin-bottom:1.5rem;">{"✏️ עריכת מתכון" if is_edit else "➕ מתכון חדש"}</h2>', unsafe_allow_html=True)
    
    # 1. מידע כללי
    with st.container():
        st.markdown('<div id="general-info-anchor"></div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([2, 1, 1])
        st.session_state.f_name = c1.text_input("שם המתכון", value=st.session_state.f_name)
        st.session_state.f_prep = c2.text_input("זמן הכנה", value=st.session_state.f_prep)
        st.session_state.f_serv = c3.text_input("מנות", value=st.session_state.f_serv)

    # 2. טבלת מצרכים דינמית
    with st.container():
        st.markdown('<div id="ingredients-container-anchor"></div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">🛒 רכיבים ומצרכים</div>', unsafe_allow_html=True)
        
        h_col1, h_col2, h_col3, _ = st.columns([2.5, 0.8, 1.2, 0.4])
        h_col1.markdown('<div style="font-weight:600; font-size:0.9rem; color:#475569;">שם המרכיב</div>', unsafe_allow_html=True)
        h_col2.markdown('<div style="font-weight:600; font-size:0.9rem; color:#475569;">כמות</div>', unsafe_allow_html=True)
        h_col3.markdown('<div style="font-weight:600; font-size:0.9rem; color:#475569;">יחידה</div>', unsafe_allow_html=True)
        
        rows_to_keep = []
        for idx, ing in enumerate(st.session_state.f_ings):
            r_col1, r_col2, r_col3, r_col4 = st.columns([2.5, 0.8, 1.2, 0.4])
            i_name = r_col1.text_input(f"שם_{idx}", value=ing["name"], key=f"ing_n_{idx}_{st.session_state.ings_version}", label_visibility="collapsed")
            i_amt = r_col2.text_input(f"כמות_{idx}", value=ing["amount"], key=f"ing_a_{idx}_{st.session_state.ings_version}", label_visibility="collapsed")
            i_unit = r_col3.text_input(f"יחידה_{idx}", value=ing["unit"], key=f"ing_u_{idx}_{st.session_state.ings_version}", label_visibility="collapsed")
            
            with r_col4:
                st.markdown('<div id="ing-delete-container-inner"></div>', unsafe_allow_html=True)
                if st.button("🗑️", key=f"ing_d_{idx}_{st.session_state.ings_version}"):
                    st.session_state.f_ings.pop(idx)
                    st.session_state.ings_version += 1
                    st.rerun()
                else:
                    rows_to_keep.append({"name": i_name, "amount": i_amt, "unit": i_unit})
        
        st.session_state.f_ings = rows_to_keep
        if st.button("➕ הוסף רכיב", key="add_ing"):
            st.session_state.f_ings.append({"name": "", "amount": "", "unit": ""})
            st.session_state.ings_version += 1
            st.rerun()

    # 3. שלבי הכנה דינמיים
    with st.container():
        st.markdown('<div id="steps-container-anchor"></div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">👨‍🍳 שלבי הכנה</div>', unsafe_allow_html=True)
        
        steps_to_keep = []
        for idx, step in enumerate(st.session_state.f_steps):
            st.markdown(f"<div style='margin-bottom:5px; font-weight:700; color:#3b82f6;'>שלב {idx+1}</div>", unsafe_allow_html=True)
            s_col1, s_col2, s_col3 = st.columns([1.5, 4, 0.4])
            s_sec = s_col1.text_input(f"כותרת חלק_{idx}", value=step["section"], key=f"st_s_{idx}_{st.session_state.steps_version}", placeholder="כותרת (למשל: לבצק)", label_visibility="collapsed")
            s_txt = s_col2.text_area(f"תוכן שלב_{idx}", value=step["text"], key=f"st_t_{idx}_{st.session_state.steps_version}", placeholder="מה עושים בשלב זה?", height=80, label_visibility="collapsed")
            
            with s_col3:
                st.markdown('<div id="step-delete-container-inner"></div>', unsafe_allow_html=True)
                if st.button("🗑️", key=f"st_d_{idx}_{st.session_state.steps_version}"):
                    st.session_state.f_steps.pop(idx)
                    st.session_state.steps_version += 1
                    st.rerun()
                else:
                    steps_to_keep.append({"section": s_sec, "text": s_txt})
                
        st.session_state.f_steps = steps_to_keep
        if st.button("➕ הוסף שלב", key="add_step"):
            st.session_state.f_steps.append({"section": "", "text": ""})
            st.session_state.steps_version += 1
            st.rerun()

    # 4. העלאת תמונת מתכון סופית
    with st.container():
        st.markdown('<div id="image-container-anchor"></div>', unsafe_allow_html=True)
        st.markdown('<div class="section-title">🖼️ תמונת המתכון הסופית</div>', unsafe_allow_html=True)
        r_img = st.file_uploader("העלה או החלף תמונה עבור ספריית המתכונים:", type=['png', 'jpg', 'jpeg'])

    # 5. כפתורי שמירה וביטול
    with st.container():
        st.markdown('<div id="actions-container-anchor"></div>', unsafe_allow_html=True)
        sc1, sc2, _ = st.columns([1.5, 1.5, 4])
        if sc1.button("💾 שמור מתכון", type="primary", use_container_width=True):
            if not st.session_state.f_name:
                st.error("נא להזין שם למתכון")
            else:
                recipe_obj = db.query(Recipe).get(st.session_state.selected_id) if is_edit else Recipe()
                recipe_obj.name = st.session_state.f_name
                recipe_obj.prep_time = st.session_state.f_prep
                recipe_obj.servings = st.session_state.f_serv
                if not is_edit: db.add(recipe_obj); db.flush()
                
                db.query(Ingredient).filter_by(recipe_id=recipe_obj.id).delete()
                db.query(Instruction).filter_by(recipe_id=recipe_obj.id).delete()
                
                for ing in st.session_state.f_ings:
                    if ing["name"].strip():
                        db.add(Ingredient(recipe_id=recipe_obj.id, name=f"{ing['amount']} | {ing['unit']} | {ing['name']}"))
                for step in st.session_state.f_steps:
                    if step["text"].strip():
                        db.add(Instruction(recipe_id=recipe_obj.id, section=step["section"] or "כללי", text=step["text"]))
                
                if r_img:
                    f_path = os.path.join(UPLOAD_DIR, f"{recipe_obj.id}_{uuid.uuid4().hex[:6]}.jpg")
                    with open(f_path, "wb") as f: f.write(r_img.getbuffer())
                    db.add(RecipeImage(recipe_id=recipe_obj.id, image_path=f_path))
                    
                db.commit()
                navigate('library')
                st.rerun()
                
        if sc2.button("❌ ביטול", use_container_width=True):

            # אם הגיעו ממסך הוספת מתכון חדש
            if not is_edit:
                navigate('select_method')

            # אם נמצאים בעריכת מתכון קיים
            else:
                navigate('view', st.session_state.selected_id)

            st.rerun()
        db.close()

    st.markdown('</div>', unsafe_allow_html=True)

# --- View Page ---
elif st.session_state.page == 'view':
    db = SessionLocal()
    r = db.query(Recipe).get(st.session_state.selected_id)
    if r:
        v_col_back, _, v_col_edit = st.columns([1, 8, 1])
        with v_col_back:
            st.markdown('<div id="view-back-container"></div>', unsafe_allow_html=True)
            if st.button("⬅️ חזרה לספרייה", key="view_back_btn"):

                try:
                    st.query_params.clear()
                except:
                    st.experimental_set_query_params()

                navigate('library')
                st.rerun()
        with v_col_edit:
            st.markdown('<div id="view-edit-container"></div>', unsafe_allow_html=True)
            if st.button("✏️ עריכה", use_container_width=False, key="view_edit_btn"):
                navigate('edit', r.id)
                st.rerun()

        img_path = r.images[-1].image_path if r.images else None
        b64_img = ""
        if img_path and os.path.exists(img_path):
            with open(img_path, "rb") as f: b64_img = base64.b64encode(f.read()).decode()
        
        bg = f"background-image: url('data:image/jpeg;base64,{b64_img}');" if b64_img else "background: #1e293b;"
        st.markdown(f'<div class="recipe-hero-container" style="{bg}"><div class="hero-overlay"><h1>{r.name}</h1><p>⏱️ {r.prep_time or "--"} | 👥 {r.servings or "--"} מנות</p></div></div>', unsafe_allow_html=True)

        c_ing, c_inst = st.columns([1, 2], gap="large")
        with c_ing:
            st.markdown('<div class="floating-card"><div class="section-title">🛒 רכיבים</div>', unsafe_allow_html=True)
            for ing in r.ingredients:
                parts = [p.strip() for p in ing.name.split('|')]
                if len(parts) >= 3:
                    st.markdown(f'<div class="ingredient-line"><span style="color:#3b82f6;">{parts[0]}</span> {parts[1]} {parts[2]}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div class="ingredient-line">🔹 {ing.name}</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
            
        with c_inst:
            st.markdown('<div class="floating-card"><div class="section-title">👨‍🍳 אופן ההכנה</div>', unsafe_allow_html=True)
            
            sections = {}
            for inst in r.instructions:
                sec = inst.section or "כללי"
                if sec not in sections: 
                    sections[sec] = []
                sections[sec].append(inst)
            
            for sec_name, steps in sections.items():
                if sec_name != "כללי":
                    st.markdown(f'<h4 style="color:#3b82f6; text-align:right; font-weight:700; margin-top:20px;">📍 {sec_name}</h4>', unsafe_allow_html=True)
                
                step_counter = 1
                for s in steps:
                    lines = [line.strip() for line in s.text.split('\n') if line.strip()]
                    for line in lines:
                        st.markdown(f'''
                        <div class="step-item">
                            <div class="step-number">{step_counter}</div>
                            <div style="flex:1; text-align:right; direction:rtl; font-size:1.05rem; color:#1e293b;">
                                {line}
                            </div>
                        </div>
                        ''', unsafe_allow_html=True)
                        step_counter += 1
            st.markdown('</div>', unsafe_allow_html=True)
    db.close()