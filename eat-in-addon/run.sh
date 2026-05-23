#!/usr/bin/with-contenv bashio

echo "Starting Eat-In Recipe Manager..."

# יצירת תיקיית מדיה בנתיב הקבוע
mkdir -p /data/media

# הרצת סקריפט הפייתון הראשי ברקע (באמצעות & בסוף השורה) כדי שלא יחסום את ה-Streamlit
python3 /app/main.py &

# הרצת ממשק המשתמש של Streamlit בנתיב המעודכן
streamlit run /app/ui.py \
  --server.port 8099 \
  --server.address 0.0.0.0 \
  --server.enableCORS false \
  --server.enableXsrfProtection false \
  --server.headless true
