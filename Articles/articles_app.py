from flask import Blueprint, redirect, render_template, request

articles_bp = Blueprint('articles', __name__, template_folder='templates')

def _canonical_redirect():
    if request.query_string:
        return redirect(request.base_url, code=301)
    return None


@articles_bp.route('/articles')
def articles():
    canonical = _canonical_redirect()
    if canonical:
        return canonical
    articles = [
        {"title": "FS!QRの基本的な考え方", "url": "/fs-qr-concept"},
        {"title": "安全な共有のポイント", "url": "/safe-sharing"},
        {"title": "暗号化の基礎知識", "url": "/encryption"},
        {"title": "教育での活用例", "url": "/education"},
        {"title": "業務での活用例", "url": "/business"},
        {"title": "リスクと対策の考え方", "url": "/risk-mitigation"},
    ]
    return render_template('articles.html', articles=articles)

@articles_bp.route('/fs-qr-concept')
def fs_qr_concept():
    return render_template('fs-qr-concept.html')

@articles_bp.route('/safe-sharing')
def safe_sharing():
    return render_template('safe-sharing.html')

@articles_bp.route('/encryption')
def encryption():
    return render_template('encryption.html')

@articles_bp.route('/education')
def education():
    return render_template('education.html')

@articles_bp.route('/business')
def business():
    return render_template('business.html')

@articles_bp.route('/risk-mitigation')
def risk_mitigation():
    return render_template('risk-mitigation.html')