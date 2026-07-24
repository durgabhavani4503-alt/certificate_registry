from pathlib import Path

# Target the exact index template path
index_path = Path("Z:/certificate_verification_project/templates/index.html")

# Define a completely safe, flat template with zero open tags
safe_html_content = """{% extends "base.html" %}

{% block title %}Upload Certificate — CertVerify{% endblock %}

{% block extra_css %}
<style>
    :root {
        --vrsec-blue: #1b498a;
        --vrsec-dark-blue: #0d256b;
        --vrsec-orange: #f15a24;
        --bg-light: #f8fafc;
        --card-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05);
        --radius-main: 16px;
    }
    .site-header {
        background: linear-gradient(135deg, var(--vrsec-blue) 0%, var(--vrsec-dark-blue) 100%) !important;
        border-bottom: 4px solid var(--vrsec-orange) !important;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08) !important;
    }
    .brand-title { color: #ffffff !important; font-weight: 800 !important; text-transform: uppercase; }
    .brand-sub { color: #94a3b8 !important; }
    .site-nav a { color: #cbd5e1 !important; }
    .site-nav a.active { color: #ffffff !important; border-bottom: 2px solid var(--vrsec-orange) !important; }
    .hero-title-section { text-align: center; margin-top: 40px; margin-bottom: 35px; }
    .upload-card-wrapper { background: #ffffff; border-radius: var(--radius-main); padding: 40px; box-shadow: var(--card-shadow); border: 1px solid #e2e8f0; text-align: center; }
    .btn-verify-submit { background-color: var(--vrsec-blue); color: white; border: none; padding: 14px 32px; border-radius: 10px; font-weight: 700; cursor: pointer; width: 100%; margin-top: 24px; }
</style>
{% endblock %}

{% block content %}
<div class="hero-title-section">
    <h2>Digital Certificate Verification Portal</h2>
    <p>Verify academic certificates using secure QR Code, Barcode, and OCR Technology nodes.</p>
</div>

<div class="upload-card-wrapper">
    <form method="post" enctype="multipart/form-data" action="{{ url_for('index') }}">
        <div style="padding: 30px; background: #f8fafc; border: 2px dashed #cbd5e1; border-radius: 12px;">
            <input type="file" name="certificate" accept=".pdf,.png,.jpg,.jpeg,.gif,.webp" required>
        </div>
        <button type="submit" class="btn-verify-submit">Execute Processing Pipeline ➔</button>
    </form>
</div>
{% endblock %}
"""

# Force write the string directly to the disk file
index_path.write_text(safe_html_content, encoding="utf-8")
print("[SUCCESS]: index.html has been completely overwritten on the disk!")
