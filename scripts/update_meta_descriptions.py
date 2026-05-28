import json, os

# Mapping of meta.description translations per language
translations = {
    "ja": "無料のファイル共有",
    "en": "Free file sharing",
    "zh-CN": "免费文件分享",
    "zh-TW": "免費檔案分享",
    "ko": "무료 파일 공유",
    "fr": "Partage de fichiers gratuit",
    "es": "Compartir archivos gratis",
    "de": "Kostenloses Dateifreigabe",
    "pt": "Compartilhamento gratuito de arquivos",
    "it": "Condivisione file gratuita",
    "ru": "Бесплатный обмен файлами",
    "nl": "Gratis bestanden delen",
    "hi": "फ़ाइल मुफ्त में साझा करें",
    "bn": "ফাইল ফ্রি শেয়ারিং",
    "vi": "Chia sẻ tệp miễn phí",
    "th": "แชร์ไฟล์ฟรี",
    "id": "Berbagi file gratis",
    "tr": "Ücretsiz dosya paylaşımı",
    "uk": "Безкоштовний обмін файлами",
    "pl": "Bezpłatne udostępnianie plików",
    "sw": "Shiriki faili bure",
    "ar": "مشاركة ملفات مجانية",
}

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
locales_dir = os.path.join(base_dir, "locales")

for lang, desc in translations.items():
    path = os.path.join(locales_dir, f"{lang}.json")
    if not os.path.exists(path):
        continue
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    ui = data.get("ui", {})
    ui["meta.description"] = desc
    data["ui"] = ui
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Updated meta.description for {lang}")
