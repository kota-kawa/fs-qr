import os
import sys

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from locale_store import load_locale_section, save_locale_section  # noqa: E402

# Mapping of meta.description translations per language
translations = {
    "ja": "FS!QRは無料で使える日本語ファイル共有サービスです。QRコード生成、グループ共有、リアルタイムノート共有で安全にデータを送信・管理できます。",
    "en": "FS!QR is a free file sharing service for QR code transfers, group file sharing, and real-time note sharing. Send and manage data securely in your browser.",
    "zh-CN": "FS!QR 是免费文件共享服务，支持二维码传输、群组文件共享和实时笔记共享，可在浏览器中安全发送和管理数据。",
    "zh-TW": "FS!QR 是免費檔案分享服務，支援 QR Code 傳輸、群組檔案分享與即時筆記分享，可在瀏覽器中安全傳送與管理資料。",
    "ko": "FS!QR은 무료 파일 공유 서비스입니다. QR 코드 전송, 그룹 파일 공유, 실시간 노트 공유로 브라우저에서 데이터를 안전하게 보내고 관리할 수 있습니다.",
    "fr": "FS!QR est un service gratuit de partage de fichiers avec transfert par QR code, partage de groupe et notes en temps réel pour gérer les données en sécurité.",
    "es": "FS!QR es un servicio gratuito para compartir archivos con códigos QR, grupos y notas en tiempo real. Envía y administra datos de forma segura en el navegador.",
    "de": "FS!QR ist ein kostenloser Dienst zur Dateifreigabe mit QR-Code-Transfer, Gruppenfreigabe und Echtzeitnotizen für sichere Datenverwaltung im Browser.",
    "pt": "FS!QR é um serviço gratuito de compartilhamento de arquivos com QR Code, grupos e notas em tempo real para enviar e gerenciar dados com segurança.",
    "it": "FS!QR è un servizio gratuito di condivisione file con QR Code, gruppi e note in tempo reale per inviare e gestire dati in modo sicuro.",
    "ru": "FS!QR — бесплатный сервис обмена файлами с QR-кодами, групповым доступом и заметками в реальном времени для безопасной работы в браузере.",
    "nl": "FS!QR is een gratis dienst voor bestanden delen met QR-codes, groepsdeling en realtime notities om gegevens veilig in de browser te beheren.",
    "hi": "FS!QR एक मुफ्त फ़ाइल साझा सेवा है, जिसमें QR कोड ट्रांसफ़र, समूह फ़ाइल साझा करना और रीयल-टाइम नोट साझा करना शामिल है।",
    "bn": "FS!QR একটি বিনামূল্যে ফাইল শেয়ারিং পরিষেবা, যেখানে QR কোড ট্রান্সফার, গ্রুপ ফাইল শেয়ারিং এবং রিয়েল-টাইম নোট শেয়ারিং আছে।",
    "vi": "FS!QR là dịch vụ chia sẻ tệp miễn phí với chuyển bằng mã QR, chia sẻ nhóm và ghi chú thời gian thực để quản lý dữ liệu an toàn.",
    "th": "FS!QR เป็นบริการแชร์ไฟล์ฟรี พร้อมส่งผ่าน QR Code แชร์ไฟล์กลุ่ม และแชร์โน้ตแบบเรียลไทม์เพื่อจัดการข้อมูลอย่างปลอดภัย",
    "id": "FS!QR adalah layanan berbagi file gratis dengan transfer QR Code, berbagi file grup, dan catatan real-time untuk mengelola data secara aman.",
    "tr": "FS!QR, QR kod aktarımı, grup dosya paylaşımı ve gerçek zamanlı not paylaşımı sunan ücretsiz bir dosya paylaşım hizmetidir.",
    "uk": "FS!QR — безкоштовний сервіс обміну файлами з QR-кодами, груповим доступом і нотатками в реальному часі для безпечної роботи в браузері.",
    "pl": "FS!QR to darmowa usługa udostępniania plików z kodami QR, udostępnianiem grupowym i notatkami w czasie rzeczywistym.",
    "sw": "FS!QR ni huduma ya kushiriki faili bila malipo yenye uhamisho wa QR Code, kushiriki kwa vikundi, na madokezo ya wakati halisi.",
    "ar": "FS!QR خدمة مجاني لمشاركة الملفات عبر رمز QR ومشاركة المجموعات والملاحظات الفورية لإرسال البيانات وإدارتها بأمان من المتصفح.",
}

base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
locales_dir = os.path.join(base_dir, "locales")

for lang, desc in translations.items():
    ui = load_locale_section(locales_dir, lang, "ui")
    ui["meta.description"] = desc
    save_locale_section(locales_dir, lang, "ui", ui)
    print(f"Updated meta.description for {lang}")
