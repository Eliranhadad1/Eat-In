#!/usr/with-contenv bashio

echo "Starting Eat-In Recipe Manager..."

# יצירת תיקיית מדיה בנתיב הקבוע של HA לשמירה קבועה שלא נמחקת בעדכונים
mkdir -p /data/media

# אתחול בסיס הנתונים (מריץ את קובץ main.py שנמצא בתוך תיקיית app)
python3 /app/main.py

# הרצת ממשק המשתמש של Streamlit עם חסימת הגנות CORS/XSRF עבור ה-Ingress של HA
streamlit run app/ui.py \
    --server.port 8099 \
    --server.address 0.0.0.0 \
    --server.enableCORS false \
    --server.enableXsrfProtection false \
    --server.headless true
