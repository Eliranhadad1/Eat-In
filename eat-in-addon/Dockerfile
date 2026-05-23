# שימוש באימג' בסיס רשמי של Home Assistant מבוסס Debian (מתאים לחבילות כבדות כמו גוגל AI)
FROM ghcr.io/home-assistant/amd64-base-debian:bookworm

# התקנת פייתון, כלי בנייה וספריות לעיבוד תמונות
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    build-essential \
    libmagic1 \
    bash \
    && rm -rf /var/lib/apt/lists/*

# הגדרת תיקיית העבודה הראשית
WORKDIR /

# העתקת קבצי הדרישות וסקריפט ההרצה
COPY requirements.txt /
COPY run.sh /

# תיקול סיומות שורות למקרה שהקובץ נערך ב-Windows
RUN sed -i 's/\r$//' /run.sh

# התקנת ספריות הפייתון (כולל הגדרת break-system-packages כי דביאן דורש את זה ב-pip הגלובלי)
RUN pip3 install --no-cache-dir --break-system-packages -r /requirements.txt

# העתקת קוד האפליקציה מהגיט לתוך תיקיית app בקונטיינר
COPY app/ /app/

# מתן הרשאות הרצה לסקריפט
RUN chmod a+x /run.sh

EXPOSE 8099

CMD [ "/bin/bash", "/run.sh" ]
