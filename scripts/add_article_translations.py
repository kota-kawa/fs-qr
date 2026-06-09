#!/usr/bin/env python3
"""新規3記事のカード文言・カテゴリを全ロケールに挿入するスクリプト。"""

import json
import re
import sys
from pathlib import Path

LOCALES_DIR = Path(__file__).parent.parent / "locales"

# 挿入するキー（日本語原文）
KEYS = {
    "category": "デジタル豆知識",
    "title1": "写真を画質を落とさずに送る方法｜送ると劣化する原因と対策",
    "desc1": "LINEやメールで写真を送ると画質が悪くなるのはなぜ？劣化する仕組みと、元の画質のまま送るための具体的な方法をiPhone・Android別にわかりやすく解説します。",
    "title2": "写真の位置情報(GPS)を削除してから送る方法｜iPhone・Android・PC別",
    "desc2": "スマホで撮った写真には撮影場所のGPS情報が埋め込まれていることをご存じですか？SNSや共有で自宅がバレるのを防ぐため、位置情報(Exif)を削除してから送る方法を端末別に解説します。",
    "title3": "KB・MB・GBの違いと容量の目安｜写真・動画は何MB？早わかり表",
    "desc3": "KB・MB・GBの違いを初心者にもわかりやすく解説。写真1枚や動画1分が何MBかの目安、メールで送れる容量、スマホの空き容量の考え方まで、具体例と早わかり表でまとめました。",
}

TRANSLATIONS: dict[str, dict[str, str]] = {
    "ja": {
        "category": "デジタル豆知識",
        "title1": "写真を画質を落とさずに送る方法｜送ると劣化する原因と対策",
        "desc1": "LINEやメールで写真を送ると画質が悪くなるのはなぜ？劣化する仕組みと、元の画質のまま送るための具体的な方法をiPhone・Android別にわかりやすく解説します。",
        "title2": "写真の位置情報(GPS)を削除してから送る方法｜iPhone・Android・PC別",
        "desc2": "スマホで撮った写真には撮影場所のGPS情報が埋め込まれていることをご存じですか？SNSや共有で自宅がバレるのを防ぐため、位置情報(Exif)を削除してから送る方法を端末別に解説します。",
        "title3": "KB・MB・GBの違いと容量の目安｜写真・動画は何MB？早わかり表",
        "desc3": "KB・MB・GBの違いを初心者にもわかりやすく解説。写真1枚や動画1分が何MBかの目安、メールで送れる容量、スマホの空き容量の考え方まで、具体例と早わかり表でまとめました。",
    },
    "en": {
        "category": "Digital Tips",
        "title1": "How to Send Photos Without Losing Quality: Why They Degrade and How to Prevent It",
        "desc1": "Why does photo quality drop when you send images via chat or email? We explain how this degradation happens and walk through concrete ways to send photos at their original quality on iPhone and Android.",
        "title2": "How to Remove GPS Location Data From Photos Before Sending: iPhone, Android, and PC",
        "desc2": "Did you know photos taken on a smartphone can carry GPS data showing where they were shot? To keep your home address from leaking through social media or shared files, we explain how to strip location (Exif) data before sending, device by device.",
        "title3": "KB, MB, and GB Explained: How Many MB Is a Photo or Video? A Quick Reference Table",
        "desc3": "A beginner-friendly explanation of the difference between KB, MB, and GB. With concrete examples and a quick-reference table, we cover how many MB a single photo or one minute of video takes, what size email can handle, and how to think about your phone's free space.",
    },
    "zh-CN": {
        "category": "数字小知识",
        "title1": "如何发送不失真的照片｜传输后画质变差的原因与解决方法",
        "desc1": "用LINE或邮件发送照片后画质为什么会变差？以iPhone和Android为例，通俗易懂地解释画质劣化的原理，以及保持原始画质发送的具体方法。",
        "title2": "发送照片前如何删除位置信息(GPS)｜iPhone・Android・PC分别说明",
        "desc2": "您知道用手机拍摄的照片中可能嵌入了拍摄地点的GPS信息吗？为了防止通过SNS或文件共享暴露住址，本文按设备分别介绍删除位置信息(Exif)后再发送的方法。",
        "title3": "KB・MB・GB的区别与容量参考｜照片和视频有多少MB？速查表",
        "desc3": "以初学者易懂的方式说明KB、MB、GB的区别。用具体示例和速查表整理了一张照片和一分钟视频的大致容量、可用邮件发送的大小上限，以及如何考虑手机剩余空间等内容。",
    },
    "zh-TW": {
        "category": "數位小知識",
        "title1": "如何傳送不失真的照片｜傳送後畫質變差的原因與解決方法",
        "desc1": "用LINE或電子郵件傳送照片後畫質為什麼會變差？以iPhone和Android為例，淺顯易懂地說明畫質劣化的原理，以及保持原始畫質傳送的具體方法。",
        "title2": "傳送照片前如何刪除位置資訊(GPS)｜iPhone・Android・PC分別說明",
        "desc2": "您知道用手機拍攝的照片可能內嵌了拍攝地點的GPS資訊嗎？為了防止透過社群媒體或檔案共享洩露住址，本文依裝置分別介紹刪除位置資訊(Exif)後再傳送的方法。",
        "title3": "KB・MB・GB的差異與容量參考｜照片和影片有多少MB？速查表",
        "desc3": "以初學者易懂的方式說明KB、MB、GB的差異。用具體範例和速查表整理了一張照片和一分鐘影片的大致容量、可用電子郵件傳送的大小上限，以及如何考量手機剩餘空間等內容。",
    },
    "ko": {
        "category": "디지털 상식",
        "title1": "사진을 화질 저하 없이 보내는 방법｜전송 시 화질이 떨어지는 이유와 대책",
        "desc1": "LINE이나 이메일로 사진을 보내면 왜 화질이 떨어질까요? 화질이 저하되는 구조와 iPhone·Android별로 원본 화질 그대로 보내는 구체적인 방법을 알기 쉽게 해설합니다.",
        "title2": "사진의 위치 정보(GPS)를 삭제하고 보내는 방법｜iPhone・Android・PC별 안내",
        "desc2": "스마트폰으로 찍은 사진에는 촬영 장소의 GPS 정보가 내장되어 있다는 사실을 알고 계셨나요? SNS나 파일 공유로 집 주소가 노출되는 것을 막기 위해, 위치 정보(Exif)를 삭제하고 보내는 방법을 기기별로 해설합니다.",
        "title3": "KB・MB・GB의 차이와 용량 기준｜사진・동영상은 몇 MB? 한눈에 보는 표",
        "desc3": "KB, MB, GB의 차이를 초보자도 알기 쉽게 해설합니다. 사진 1장이나 동영상 1분이 몇 MB인지의 목안, 이메일로 보낼 수 있는 용량, 스마트폰 여유 공간 생각하는 방법까지 구체적인 예시와 한눈에 보는 표로 정리했습니다.",
    },
    "fr": {
        "category": "Astuces numériques",
        "title1": "Comment envoyer des photos sans perte de qualité | Pourquoi elles se dégradent et comment l'éviter",
        "desc1": "Pourquoi la qualité des photos se dégrade-t-elle lorsqu'on les envoie par messagerie ou e-mail ? Nous expliquons simplement le mécanisme de compression et les méthodes concrètes pour envoyer des photos en qualité originale sur iPhone et Android.",
        "title2": "Supprimer les données de localisation GPS d'une photo avant de l'envoyer | iPhone, Android et PC",
        "desc2": "Saviez-vous que les photos prises sur smartphone peuvent contenir des données GPS indiquant l'endroit où elles ont été prises ? Pour éviter que votre domicile ne soit localisable via les réseaux sociaux ou le partage de fichiers, nous expliquons comment supprimer ces informations de localisation (Exif) avant l'envoi, selon votre appareil.",
        "title3": "Différence entre Ko, Mo et Go et repères de taille | Combien de Mo pèse une photo ou une vidéo ? Tableau récapitulatif",
        "desc3": "Une explication claire des différences entre Ko, Mo et Go, même pour les débutants. Avec des exemples concrets et un tableau récapitulatif couvrant le poids d'une photo, d'une minute de vidéo, la limite d'une pièce jointe par e-mail et comment gérer l'espace disponible sur son smartphone.",
    },
    "es": {
        "category": "Consejos digitales",
        "title1": "Cómo enviar fotos sin perder calidad | Por qué se degradan y cómo evitarlo",
        "desc1": "¿Por qué la calidad de las fotos empeora al enviarlas por chat o correo? Explicamos el mecanismo de degradación y los métodos concretos para enviar imágenes en calidad original, tanto en iPhone como en Android.",
        "title2": "Cómo eliminar la ubicación GPS de las fotos antes de compartirlas | iPhone, Android y PC",
        "desc2": "¿Sabías que las fotos tomadas con el móvil pueden llevar incorporada la ubicación GPS donde fueron tomadas? Para evitar que tu domicilio quede expuesto en redes sociales o al compartir archivos, explicamos cómo eliminar los datos de ubicación (Exif) antes de enviarlas, según el dispositivo.",
        "title3": "Diferencia entre KB, MB y GB y referencia de tamaños | ¿Cuántos MB ocupa una foto o video? Tabla rápida",
        "desc3": "Una explicación clara de las diferencias entre KB, MB y GB, incluso para principiantes. Con ejemplos concretos y una tabla rápida que cubre el peso de una foto, un minuto de vídeo, el límite de un adjunto de correo y cómo gestionar el espacio libre del móvil.",
    },
    "de": {
        "category": "Digitale Tipps",
        "title1": "Fotos ohne Qualitätsverlust senden | Warum Bilder schlechter werden und wie man es verhindert",
        "desc1": "Warum verschlechtert sich die Bildqualität beim Versenden per Chat oder E-Mail? Wir erklären, wie Kompression funktioniert, und zeigen konkrete Wege, Fotos in Originalqualität auf iPhone und Android zu versenden.",
        "title2": "GPS-Standortdaten aus Fotos entfernen vor dem Senden | iPhone, Android und PC",
        "desc2": "Wussten Sie, dass Smartphone-Fotos oft GPS-Koordinaten des Aufnahmeorts enthalten? Um zu verhindern, dass Ihre Wohnadresse über soziale Medien oder Dateifreigaben preisgegeben wird, erklären wir gerätebezogen, wie Sie Standortdaten (Exif) vor dem Senden entfernen.",
        "title3": "Unterschied zwischen KB, MB und GB und Größenrichtwerte | Wie viele MB hat ein Foto oder Video? Schnellübersicht",
        "desc3": "Eine verständliche Erklärung der Unterschiede zwischen KB, MB und GB, auch für Einsteiger. Mit konkreten Beispielen und einer Schnellübersicht über das Gewicht eines Fotos, einer Videominute, E-Mail-Anhangslimits und der Speicherverwaltung auf dem Smartphone.",
    },
    "pt": {
        "category": "Dicas digitais",
        "title1": "Como enviar fotos sem perder qualidade | Por que elas se degradam e como evitar",
        "desc1": "Por que a qualidade das fotos piora ao enviá-las por mensagem ou e-mail? Explicamos o mecanismo de degradação e as formas concretas de enviar fotos em qualidade original no iPhone e Android.",
        "title2": "Como remover dados de localização GPS de fotos antes de enviar | iPhone, Android e PC",
        "desc2": "Você sabia que fotos tiradas com smartphone podem conter informações de GPS do local de captura? Para evitar que seu endereço seja exposto em redes sociais ou ao compartilhar arquivos, explicamos como remover dados de localização (Exif) antes de enviá-las, por tipo de dispositivo.",
        "title3": "Diferença entre KB, MB e GB e referência de tamanhos | Quantos MB tem uma foto ou vídeo? Tabela rápida",
        "desc3": "Uma explicação clara das diferenças entre KB, MB e GB, mesmo para iniciantes. Com exemplos concretos e uma tabela rápida sobre o tamanho de uma foto, um minuto de vídeo, o limite de anexo de e-mail e como gerenciar o espaço livre do smartphone.",
    },
    "it": {
        "category": "Consigli digitali",
        "title1": "Come inviare foto senza perdita di qualità | Perché si degradano e come evitarlo",
        "desc1": "Perché la qualità delle foto peggiora quando le si invia via chat o e-mail? Spieghiamo il meccanismo della compressione e i metodi concreti per inviare foto in qualità originale su iPhone e Android.",
        "title2": "Come rimuovere i dati GPS dalle foto prima di inviarle | iPhone, Android e PC",
        "desc2": "Sapevi che le foto scattate con smartphone possono contenere informazioni GPS sulla posizione di scatto? Per evitare che il tuo indirizzo di casa sia esposto tramite social o condivisione file, spieghiamo come rimuovere i dati di posizione (Exif) prima dell'invio, per ciascun tipo di dispositivo.",
        "title3": "Differenza tra KB, MB e GB e riferimenti di dimensione | Quanti MB pesa una foto o un video? Tabella di riferimento",
        "desc3": "Una spiegazione chiara delle differenze tra KB, MB e GB, anche per i principianti. Con esempi concreti e una tabella di riferimento sul peso di una foto, un minuto di video, il limite degli allegati email e come gestire lo spazio libero sullo smartphone.",
    },
    "vi": {
        "category": "Mẹo kỹ thuật số",
        "title1": "Cách gửi ảnh mà không làm giảm chất lượng | Tại sao ảnh bị giảm chất lượng và cách khắc phục",
        "desc1": "Tại sao chất lượng ảnh giảm khi gửi qua tin nhắn hoặc email? Chúng tôi giải thích cơ chế nén ảnh và các phương pháp cụ thể để gửi ảnh với chất lượng gốc trên iPhone và Android.",
        "title2": "Cách xóa thông tin vị trí GPS khỏi ảnh trước khi gửi | iPhone, Android và PC",
        "desc2": "Bạn có biết ảnh chụp bằng điện thoại có thể chứa thông tin GPS về nơi chụp không? Để tránh lộ địa chỉ nhà qua mạng xã hội hoặc chia sẻ tệp, chúng tôi hướng dẫn cách xóa thông tin vị trí (Exif) trước khi gửi, theo từng thiết bị.",
        "title3": "Sự khác biệt giữa KB, MB và GB và mức tham chiếu dung lượng | Ảnh và video chiếm bao nhiêu MB? Bảng tra nhanh",
        "desc3": "Giải thích dễ hiểu về sự khác biệt giữa KB, MB và GB, ngay cả với người mới bắt đầu. Gồm ví dụ cụ thể và bảng tra nhanh về dung lượng một ảnh, một phút video, giới hạn đính kèm email và cách quản lý bộ nhớ điện thoại.",
    },
    "th": {
        "category": "เกร็ดความรู้ดิจิทัล",
        "title1": "วิธีส่งภาพโดยไม่ลดคุณภาพ | สาเหตุที่ภาพเสื่อมคุณภาพเมื่อส่งและวิธีแก้ไข",
        "desc1": "ทำไมคุณภาพรูปภาพถึงลดลงเมื่อส่งผ่านแชทหรืออีเมล? เราอธิบายกลไกการบีบอัดและวิธีการส่งภาพคุณภาพต้นฉบับบน iPhone และ Android อย่างชัดเจน",
        "title2": "วิธีลบข้อมูลตำแหน่ง GPS จากรูปภาพก่อนส่ง | iPhone, Android และ PC",
        "desc2": "คุณรู้ไหมว่าภาพถ่ายจากสมาร์ตโฟนอาจมีข้อมูล GPS ของสถานที่ถ่ายภาพฝังอยู่? เพื่อป้องกันไม่ให้ที่อยู่บ้านของคุณถูกเปิดเผยผ่านโซเชียลมีเดียหรือการแชร์ไฟล์ เราอธิบายวิธีลบข้อมูลตำแหน่ง (Exif) ก่อนส่ง แยกตามอุปกรณ์",
        "title3": "ความแตกต่างระหว่าง KB, MB และ GB และขนาดอ้างอิง | ภาพและวิดีโอใช้พื้นที่กี่ MB? ตารางอ้างอิงด่วน",
        "desc3": "คำอธิบายที่ชัดเจนเกี่ยวกับความแตกต่างระหว่าง KB, MB และ GB สำหรับผู้เริ่มต้น พร้อมตัวอย่างและตารางอ้างอิงด่วนเกี่ยวกับขนาดภาพหนึ่งรูป วิดีโอหนึ่งนาที ขีดจำกัดไฟล์แนบอีเมล และการจัดการพื้นที่ว่างบนสมาร์ตโฟน",
    },
    "id": {
        "category": "Tips Digital",
        "title1": "Cara Mengirim Foto Tanpa Menurunkan Kualitas | Penyebab Penurunan Kualitas dan Solusinya",
        "desc1": "Mengapa kualitas foto menurun saat dikirim via pesan atau email? Kami menjelaskan mekanisme kompresi dan cara konkret mengirim foto dengan kualitas asli di iPhone dan Android.",
        "title2": "Cara Menghapus Data Lokasi GPS dari Foto Sebelum Mengirim | iPhone, Android, dan PC",
        "desc2": "Tahukah Anda bahwa foto yang diambil dengan smartphone bisa mengandung informasi GPS lokasi pemotretan? Untuk mencegah alamat rumah Anda terungkap melalui media sosial atau berbagi file, kami menjelaskan cara menghapus data lokasi (Exif) sebelum mengirim, per jenis perangkat.",
        "title3": "Perbedaan KB, MB, dan GB serta Panduan Ukuran File | Berapa MB Foto dan Video? Tabel Referensi Cepat",
        "desc3": "Penjelasan mudah tentang perbedaan KB, MB, dan GB bahkan untuk pemula. Dilengkapi contoh nyata dan tabel referensi cepat tentang ukuran satu foto, satu menit video, batas lampiran email, dan cara mengelola ruang kosong di smartphone.",
    },
    "tr": {
        "category": "Dijital İpuçları",
        "title1": "Fotoğrafları Kalite Kaybetmeden Gönderme | Neden Bozulur ve Nasıl Önlenir",
        "desc1": "Mesaj veya e-posta ile gönderilen fotoğrafların kalitesi neden düşer? Sıkıştırma mekanizmasını ve iPhone ile Android'de fotoğrafları orijinal kalitede göndermenin somut yollarını açıklıyoruz.",
        "title2": "Fotoğraflardaki GPS Konum Bilgisini Göndermeden Önce Silme | iPhone, Android ve PC",
        "desc2": "Akıllı telefonla çekilen fotoğrafların GPS konum bilgisi içerebileceğini biliyor muydunuz? Ev adresinizin sosyal medya veya dosya paylaşımı yoluyla ifşa olmasını önlemek için, konum bilgisini (Exif) göndermeden önce nasıl sileceğinizi cihaz bazında açıklıyoruz.",
        "title3": "KB, MB ve GB Farkı ve Boyut Referansları | Fotoğraf ve Video Kaç MB? Hızlı Başvuru Tablosu",
        "desc3": "KB, MB ve GB arasındaki farkların yeni başlayanlar için bile anlaşılır bir açıklaması. Bir fotoğrafın, bir dakika videonun boyutu, e-posta ek limiti ve akıllı telefondaki boş alanı yönetme hakkında somut örnekler ve hızlı başvuru tablosu içerir.",
    },
    "uk": {
        "category": "Цифрові поради",
        "title1": "Як надсилати фото без втрати якості | Чому якість погіршується і як цьому запобігти",
        "desc1": "Чому якість фото погіршується при надсиланні через чат або email? Ми пояснюємо механізм стиснення та конкретні способи надсилання фото в оригінальній якості на iPhone і Android.",
        "title2": "Як видалити GPS-геодані з фото перед відправкою | iPhone, Android та PC",
        "desc2": "Чи знаєте ви, що фотографії, зроблені смартфоном, можуть містити GPS-координати місця зйомки? Щоб запобігти розкриттю вашої домашньої адреси через соцмережі або спільний доступ до файлів, пояснюємо, як видалити геодані (Exif) перед надсиланням — для кожного типу пристрою.",
        "title3": "Різниця між КБ, МБ і ГБ та орієнтири розмірів | Скільки МБ важать фото і відео? Швидка таблиця",
        "desc3": "Зрозуміле пояснення різниці між КБ, МБ і ГБ навіть для початківців. Конкретні приклади і таблиця для швидкої довідки про розмір фото, хвилини відео, ліміт вкладень в email і керування вільним місцем на смартфоні.",
    },
    "ru": {
        "category": "Цифровые советы",
        "title1": "Как отправлять фото без потери качества | Почему происходит ухудшение и как его предотвратить",
        "desc1": "Почему качество фотографий ухудшается при отправке через мессенджер или email? Объясняем механизм сжатия и конкретные способы отправки фото в оригинальном качестве на iPhone и Android.",
        "title2": "Как удалить GPS-геоданные из фото перед отправкой | iPhone, Android и ПК",
        "desc2": "Знаете ли вы, что фотографии, снятые смартфоном, могут содержать GPS-координаты места съёмки? Чтобы ваш домашний адрес не стал общедоступным через соцсети или файловые сервисы, объясняем, как удалить геоданные (Exif) перед отправкой — для каждого типа устройства.",
        "title3": "Разница между КБ, МБ и ГБ и ориентиры по размерам файлов | Сколько МБ весят фото и видео? Таблица для быстрой справки",
        "desc3": "Понятное объяснение разницы между КБ, МБ и ГБ даже для новичков. Конкретные примеры и таблица для быстрого поиска: сколько весит фото, минута видео, лимит вложений в email и как управлять свободным местом на смартфоне.",
    },
    "nl": {
        "category": "Digitale tips",
        "title1": "Foto's verzenden zonder kwaliteitsverlies | Waarom ze verslechteren en hoe je dat voorkomt",
        "desc1": "Waarom verslechtert de fotokwaliteit bij verzending via chat of e-mail? We leggen het compressiemechanisme uit en geven concrete manieren om foto's in originele kwaliteit te verzenden op iPhone en Android.",
        "title2": "GPS-locatiegegevens verwijderen uit foto's voor verzending | iPhone, Android en pc",
        "desc2": "Wist u dat foto's gemaakt met een smartphone GPS-locatiegegevens van de opnamelocatie kunnen bevatten? Om te voorkomen dat uw thuisadres via sociale media of bestandsdeling wordt onthuld, leggen we per apparaattype uit hoe u locatiegegevens (Exif) verwijdert voor het verzenden.",
        "title3": "Verschil tussen KB, MB en GB en grootte-referenties | Hoeveel MB zijn foto en video? Snelle referentietabel",
        "desc3": "Een duidelijke uitleg van het verschil tussen KB, MB en GB, ook voor beginners. Met concrete voorbeelden en een snelle referentietabel over de grootte van een foto, een minuut video, de limiet voor e-mailbijlagen en hoe je de vrije ruimte op je smartphone beheert.",
    },
    "hi": {
        "category": "डिजिटल टिप्स",
        "title1": "फ़ोटो बिना गुणवत्ता खोए भेजने का तरीका | भेजने पर खराब होने के कारण और समाधान",
        "desc1": "चैट या ईमेल से फ़ोटो भेजने पर गुणवत्ता क्यों घटती है? हम कम्प्रेशन के तंत्र और iPhone व Android पर मूल गुणवत्ता में फ़ोटो भेजने के ठोस तरीके समझाते हैं।",
        "title2": "फ़ोटो भेजने से पहले GPS स्थान जानकारी हटाने का तरीका | iPhone, Android और PC",
        "desc2": "क्या आप जानते हैं कि स्मार्टफोन से ली गई तस्वीरों में शूटिंग स्थान की GPS जानकारी एम्बेड हो सकती है? SNS या फ़ाइल शेयरिंग के ज़रिए अपना घर का पता उजागर होने से बचाने के लिए, हम डिवाइस के अनुसार भेजने से पहले स्थान जानकारी (Exif) हटाने का तरीका बताते हैं।",
        "title3": "KB, MB और GB का अंतर और फ़ाइल साइज़ की जानकारी | फ़ोटो और वीडियो कितने MB के होते हैं? त्वरित संदर्भ तालिका",
        "desc3": "KB, MB और GB के अंतर की सरल व्याख्या, नए उपयोगकर्ताओं के लिए भी। एक फ़ोटो, एक मिनट के वीडियो का आकार, ईमेल अटैचमेंट की सीमा और स्मार्टफोन पर खाली जगह प्रबंधित करने के तरीके — ठोस उदाहरणों और त्वरित संदर्भ तालिका के साथ।",
    },
    "bn": {
        "category": "ডিজিটাল টিপস",
        "title1": "মান না কমিয়ে ছবি পাঠানোর পদ্ধতি | পাঠালে কেন মান কমে এবং সমাধান",
        "desc1": "চ্যাট বা ইমেলে ছবি পাঠালে মান কেন কমে? আমরা কম্প্রেশনের কার্যপদ্ধতি এবং iPhone ও Android-এ মূল মানে ছবি পাঠানোর সুনির্দিষ্ট উপায় ব্যাখ্যা করি।",
        "title2": "ছবি পাঠানোর আগে GPS অবস্থান তথ্য মুছে ফেলার পদ্ধতি | iPhone, Android ও PC",
        "desc2": "আপনি কি জানেন যে স্মার্টফোনে তোলা ছবিতে তোলার স্থানের GPS তথ্য এম্বেড থাকতে পারে? SNS বা ফাইল শেয়ারিংয়ের মাধ্যমে বাড়ির ঠিকানা ফাঁস হওয়া ঠেকাতে, ডিভাইসভেদে পাঠানোর আগে অবস্থান তথ্য (Exif) মুছে ফেলার পদ্ধতি ব্যাখ্যা করি।",
        "title3": "KB, MB ও GB-এর পার্থক্য এবং ফাইল সাইজের নির্দেশিকা | ছবি ও ভিডিও কত MB? দ্রুত রেফারেন্স টেবিল",
        "desc3": "KB, MB ও GB-এর পার্থক্যের সহজ ব্যাখ্যা, নতুনদের জন্যও। একটি ছবি ও এক মিনিটের ভিডিওর আকার, ইমেইল সংযুক্তির সীমা এবং স্মার্টফোনে খালি জায়গা পরিচালনার উপায় — নির্দিষ্ট উদাহরণ ও দ্রুত রেফারেন্স টেবিলসহ।",
    },
    "pl": {
        "category": "Porady cyfrowe",
        "title1": "Jak wysyłać zdjęcia bez utraty jakości | Dlaczego się degradują i jak temu zapobiec",
        "desc1": "Dlaczego jakość zdjęć pogarsza się przy wysyłaniu przez czat lub e-mail? Wyjaśniamy mechanizm kompresji i konkretne sposoby wysyłania zdjęć w oryginalnej jakości na iPhone i Android.",
        "title2": "Jak usunąć dane GPS z zdjęć przed wysłaniem | iPhone, Android i PC",
        "desc2": "Czy wiesz, że zdjęcia zrobione smartfonem mogą zawierać informacje GPS o miejscu wykonania? Aby zapobiec ujawnieniu adresu domowego poprzez media społecznościowe lub udostępnianie plików, wyjaśniamy, jak usunąć dane lokalizacyjne (Exif) przed wysłaniem, w zależności od urządzenia.",
        "title3": "Różnica między KB, MB i GB oraz wzorce rozmiarów | Ile MB ma zdjęcie i film? Tabela szybkiej pomocy",
        "desc3": "Zrozumiałe wyjaśnienie różnicy między KB, MB i GB nawet dla początkujących. Z konkretnymi przykładami i tabelą szybkiej pomocy dotyczącą rozmiaru zdjęcia, minuty wideo, limitu załączników e-mail i zarządzania wolnym miejscem na smartfonie.",
    },
    "sw": {
        "category": "Vidokezo vya Kidijitali",
        "title1": "Jinsi ya Kutuma Picha Bila Kupoteza Ubora | Kwa Nini Zinachakaa na Jinsi ya Kuzuia",
        "desc1": "Kwa nini ubora wa picha hupungua zinapotumwa kwa meseji au barua pepe? Tunaelezea mfumo wa ukandamizaji na njia halisi za kutuma picha kwa ubora wa asili kwenye iPhone na Android.",
        "title2": "Jinsi ya Kufuta Taarifa za Mahali (GPS) Kutoka Picha Kabla ya Kutuma | iPhone, Android na PC",
        "desc2": "Je, unajua kwamba picha zilizopigwa na simu mahiri zinaweza kuwa na taarifa za GPS za mahali zilipopigwa? Ili kuzuia anwani ya nyumba yako kuonekana kupitia mitandao ya kijamii au kushiriki faili, tunaelezea jinsi ya kufuta taarifa za mahali (Exif) kabla ya kutuma, kulingana na kifaa.",
        "title3": "Tofauti Kati ya KB, MB na GB na Mwongozo wa Ukubwa | Picha na Video Ni MB Ngapi? Jedwali la Haraka",
        "desc3": "Maelezo rahisi ya tofauti kati ya KB, MB na GB hata kwa wanaoanza. Pamoja na mifano halisi na jedwali la haraka kuhusu ukubwa wa picha moja, dakika moja ya video, kikomo cha kiambatisho cha barua pepe, na jinsi ya kudhibiti nafasi ya simu.",
    },
    "ar": {
        "category": "نصائح رقمية",
        "title1": "كيفية إرسال الصور دون فقدان الجودة | أسباب التدهور وكيفية منعه",
        "desc1": "لماذا تنخفض جودة الصور عند إرسالها عبر الرسائل أو البريد الإلكتروني؟ نشرح آلية الضغط والطرق العملية لإرسال الصور بجودتها الأصلية على iPhone وAndroid.",
        "title2": "كيفية حذف بيانات الموقع (GPS) من الصور قبل إرسالها | iPhone وAndroid وPC",
        "desc2": "هل تعلم أن الصور الملتقطة بالهاتف الذكي قد تحتوي على بيانات GPS لمكان التصوير؟ لمنع انكشاف عنوان منزلك عبر وسائل التواصل الاجتماعي أو مشاركة الملفات، نشرح كيفية حذف بيانات الموقع (Exif) قبل الإرسال، وفقاً لنوع الجهاز.",
        "title3": "الفرق بين KB وMB وGB ومرجع الأحجام | كم MB تشغل الصورة والفيديو؟ جدول مرجع سريع",
        "desc3": "شرح واضح لاختلافات KB وMB وGB حتى للمبتدئين. مع أمثلة عملية وجدول مرجع سريع يغطي حجم صورة واحدة، ودقيقة من الفيديو، وحد مرفقات البريد الإلكتروني، وكيفية إدارة المساحة الحرة على الهاتف.",
    },
}

ANCHOR_KEY = "ビジネス"


def insert_entries(lang: str, translations: dict[str, str]) -> bool:
    path = LOCALES_DIR / f"{lang}.json"
    if not path.exists():
        print(f"  SKIP: {path} not found", file=sys.stderr)
        return False

    text = path.read_text(encoding="utf-8")

    # すでに挿入済みならスキップ
    if KEYS["category"] in text and translations["category"] in text:
        already = True
        # カテゴリ訳が既に入っているか確認
        for v in translations.values():
            if v not in text:
                already = False
                break
        if already:
            print(f"  {lang}: already up-to-date, skipping")
            return True

    # 独立したカテゴリラベル行を探す。
    # パターン: 行頭スペース + "ビジネス": "値"
    pattern = re.compile(
        r'(\s+"ビジネス"\s*:\s*"[^"]*"\s*,?\s*\n)',
        re.MULTILINE,
    )
    match = pattern.search(text)
    if not match:
        print(f"  {lang}: anchor not found, skipping", file=sys.stderr)
        return False

    insert_pos = match.end()

    def json_line(k: str, v: str) -> str:
        return f"    {json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)},\n"

    new_lines = (
        json_line(KEYS["category"], translations["category"])
        + json_line(KEYS["title1"], translations["title1"])
        + json_line(KEYS["desc1"], translations["desc1"])
        + json_line(KEYS["title2"], translations["title2"])
        + json_line(KEYS["desc2"], translations["desc2"])
        + json_line(KEYS["title3"], translations["title3"])
        + json_line(KEYS["desc3"], translations["desc3"])
    )

    new_text = text[:insert_pos] + new_lines + text[insert_pos:]
    path.write_text(new_text, encoding="utf-8")
    print(f"  {lang}: inserted 7 entries")
    return True


def main() -> None:
    for lang, translations in TRANSLATIONS.items():
        if lang == "en":
            # en はすでに手動で追加済み
            print("  en: already done")
            continue
        insert_entries(lang, translations)


if __name__ == "__main__":
    main()
