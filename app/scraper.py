import os
import json
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from PIL import Image

GEMINI_MODEL = "gemini-1.5-flash"

SYSTEM_PROMPT = """Analyze this recipe source and return ONLY a valid JSON object — no markdown, no backticks, no extra text.
Required format:
{
  "name": "שם המתכון",
  "prep_time": "זמן הכנה",
  "cook_time": "זמן בישול",
  "servings": "מספר מנות",
  "ingredients": [
    {"amount": "1", "unit": "כוס", "name": "קמח", "note": ""}
  ],
  "instructions": [
    {"section": "שם קטע", "text": "תיאור השלב"}
  ],
  "tags": ["תג1", "תג2"]
}
Use Hebrew for all text values. If a field is unknown, use an empty string."""


def get_api_key() -> str:
    try:
        with open('/data/options.json') as f:
            return json.load(f).get('gemini_api_key', '')
    except Exception:
        return os.environ.get("GEMINI_API_KEY", "")


def _configure():
    api_key = get_api_key()
    if not api_key:
        raise ValueError("מפתח Gemini API לא מוגדר. הגדר אותו בהגדרות התוסף.")
    genai.configure(api_key=api_key)
    # שימוש במשתנה הגלובלי המעודכן
    return genai.GenerativeModel(GEMINI_MODEL)


def _clean_json(raw: str) -> dict:
    cleaned = raw.strip().replace('```json', '').replace('```', '').strip()
    return json.loads(cleaned)


def from_url(url: str) -> dict | None:
    """Fetch a recipe from a URL using BeautifulSoup + Gemini."""
    model = _configure()
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; EatInBot/1.0)'}
    resp = requests.get(url, timeout=15, headers=headers)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    # Remove noise
    for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'advertisement']):
        tag.decompose()
    content = soup.get_text(separator=' ', strip=True)[:7000]
    result = model.generate_content(f"{SYSTEM_PROMPT}\n\nURL: {url}\n\nPage text:\n{content}")
    return _clean_json(result.text)


def from_image(image_path: str) -> dict | None:
    """Extract a recipe from an image file using Gemini Vision."""
    model = _configure()
    img = Image.open(image_path)
    result = model.generate_content([SYSTEM_PROMPT, img])
    return _clean_json(result.text)


def from_pil_image(pil_image) -> dict | None:
    """Extract a recipe from a PIL Image object (e.g. from st.file_uploader)."""
    model = _configure()
    result = model.generate_content([SYSTEM_PROMPT, pil_image])
    return _clean_json(result.text)


def from_text(text: str) -> dict | None:
    """Parse a recipe from free-form text."""
    model = _configure()
    result = model.generate_content(f"{SYSTEM_PROMPT}\n\nRecipe text:\n{text}")
    return _clean_json(result.text)


# Legacy compatibility shim used by older ui.py versions
def process_recipe_source(input_data) -> dict | None:
    try:
        if isinstance(input_data, str) and input_data.startswith('http'):
            return from_url(input_data)
        else:
            return from_image(input_data)
    except Exception as e:
        print(f"Scraper error: {e}")
        return None