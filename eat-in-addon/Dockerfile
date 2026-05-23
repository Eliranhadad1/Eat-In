# שימוש באימג' בסיס רשמי של Home Assistant ל-Python (תומך בכל הארכיטקטורות אוטומטית)
FROM ghcr.io/home-assistant/amd64-base-python:3.11-alpine3.19

# התקנת כלים לעיבוד תמונות ובנייה (משתמשים ב-apk כי האימג' מבוסס Alpine, קל ומהיר בהרבה)
RUN apk add --no-cache \
    build-base \
    libmagic \
    bash

# הגדרת תיקיית העבודה הראשית בקונטיינר
WORKDIR /

# העתקת קבצי הדרישות וסקריפט ההרצה לתיקיית השורש
COPY requirements.txt /
COPY run.sh /

# התקנת ספריות הפייתון
RUN pip install --no-cache-dir -r /requirements.txt

# העתקת תוכן תיקיית app שבגיט ישירות לתוך תיקיית app בקונטיינר
COPY app/ /app/

# מתן הרשאות הרצה לסקריפט ההפעלה
RUN chmod a+x /run.sh

# חשיפת הפורט של האפליקציה עבור ה-Ingress של HA
EXPOSE 8099

# הפעלה של הסקריפט מתיקיית השורש
CMD [ "/bin/bash", "/run.sh" ]
