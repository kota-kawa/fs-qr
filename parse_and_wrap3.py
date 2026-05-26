import os
import glob
import re

ARTICLES_DIR = "Articles/templates"

for filepath in glob.glob(os.path.join(ARTICLES_DIR, "*.html")):
    if "_article_base.html" in filepath or "_article_cta.html" in filepath or "articles.html" in filepath:
        continue

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    def replace_text(match):
        pre = match.group(1)
        text = match.group(2).strip()
        post = match.group(3)
        if not text:
            return match.group(0)
        if "{{" in text:
            return match.group(0)
        return f"{pre}{{{{ t('{text}') }}}}{post}"

    # Match <h2 class="mb-4">...</h2>
    content = re.sub(r'(<h2[^>]*>)([^<]+)(</h2>)', replace_text, content)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
