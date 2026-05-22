FROM python:3.11-slim-bookworm

# התקנת כלים לעיבוד תמונות ובנייה
RUN apt-get update && apt-get install -y \
    build-essential \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# התקנת ספריות
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# העתקת כל הקוד מהמחשב/גיט לתוך תיקיית /app בקונטיינר
COPY . .

# מתן הרשאות הרצה לסקריפט ההפעלה
RUN chmod a+x run.sh

# חשיפת הפורט של האפליקציה עבור ה-Ingress של HA
EXPOSE 8099

# הפעלה מפורשת באמצעות Bash
CMD [ "/bin/bash", "./run.sh" ]