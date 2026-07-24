import os
import uuid
import csv
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.utils import secure_filename

from extractor import extract_certificates
from pipeline import analyze_certificates
from modules.history_module import (
    get_dashboard_stats,
    init_history_table,
    list_verification_history,
    save_upload_history,
)
from database.db_utils import init_database
from database.import_from_csv import import_csv

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_FOLDER = BASE_DIR / "uploads"
ORIGINALS_FOLDER = UPLOAD_FOLDER / "originals"
EXTRACTED_FOLDER = UPLOAD_FOLDER / "extracted"
VERIFIED_FOLDER = BASE_DIR / "verified_certificates"
DATABASE_UPLOAD_FOLDER = BASE_DIR / "database_uploads"
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "gif", "webp"}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-me-in-production")
app.config["UPLOAD_FOLDER"] = str(UPLOAD_FOLDER)
DATABASE = os.path.join(str(BASE_DIR), 'database.db')
app.config['DATABASE'] = DATABASE

for folder in (
    UPLOAD_FOLDER,
    ORIGINALS_FOLDER,
    EXTRACTED_FOLDER,
    VERIFIED_FOLDER,
    DATABASE_UPLOAD_FOLDER,
):
    folder.mkdir(parents=True, exist_ok=True)

init_database()
init_history_table()


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _relative_upload_path(path: Path) -> str:
    return path.relative_to(UPLOAD_FOLDER).as_posix()


@app.route("/", methods=["GET", "POST"])
def index():
    last_extraction = session.get("last_extraction")

    if request.method == "POST":
        if "certificate" not in request.files:
            flash("No file part in the request.", "error")
            return redirect(url_for("index"))

        file = request.files["certificate"]

        if file.filename == "":
            flash("No file selected.", "error")
            return redirect(url_for("index"))

        if not allowed_file(file.filename):
            flash("Only PDF and image files are allowed.", "error")
            return redirect(url_for("index"))

        batch_id = uuid.uuid4().hex[:8]
        filename = secure_filename(file.filename) or "upload"
        original_path = ORIGINALS_FOLDER / f"{batch_id}_{filename}"
        file.save(original_path)

        output_dir = EXTRACTED_FOLDER / batch_id
        try:
            extracted_paths = extract_certificates(original_path, output_dir)
        except Exception as exc:
            flash(f"Upload saved but extraction failed: {exc}", "error")
            return redirect(url_for("index"))

        relative_files = [_relative_upload_path(path) for path in extracted_paths]
        result = {
            "batch_id": batch_id,
            "original": _relative_upload_path(original_path),
            "count": len(extracted_paths),
            "files": relative_files,
            "certificate_entries": [],
        }

        # QR first (pyzbar), then OCR fallback — see pipeline.py.
        verified_batch_dir = VERIFIED_FOLDER / batch_id
        try:
            result["certificate_entries"] = analyze_certificates(
                original_path,
                extracted_paths,
                relative_files,
                verified_output_dir=verified_batch_dir,
            )
        except FileNotFoundError as exc:
            flash(str(exc), "error")
        except Exception as exc:
            flash(f"Certificate(s) saved but reading failed: {exc}", "error")

        if result["certificate_entries"]:
            save_upload_history(batch_id, filename, result["certificate_entries"])

        session["last_extraction"] = result

        flash(
            f"Uploaded {filename} and extracted {len(extracted_paths)} certificate(s). "
            f"View results on the dashboard.",
            "success",
        )
        return redirect(url_for("index"))

    return render_template("index.html", last_extraction=last_extraction)


@app.route("/dashboard")
def dashboard():
    """Renders the core metrics tracking overview center panel."""
    history_records = list_verification_history()
    stats_dict = get_dashboard_stats()
    return render_template("dashboard.html", history=history_records, stats=stats_dict)


@app.route("/verified/<batch_id>/<path:filename>")
def serve_verified_copy(batch_id: str, filename: str):
    """Serve verified digital copies (originals stay in uploads/)."""
    batch_dir = VERIFIED_FOLDER / batch_id
    return send_from_directory(batch_dir, filename)


@app.route("/import_database", methods=["POST"])
def import_database():
    """Ingests the CSV database sheet. Processes standard formats instantly or falls back to column mapping."""
    if "csv_file" not in request.files:
        flash("No file part in the request.", "error")
        return redirect(url_for("dashboard"))

    file = request.files["csv_file"]

    if file.filename == "":
        flash("Please choose a CSV file.", "error")
        return redirect(url_for("dashboard"))

    if not file.filename.lower().endswith(".csv"):
        flash("Only standard CSV database sheets are supported.", "error")
        return redirect(url_for("dashboard"))

    filename = secure_filename(file.filename) or "temp_import.csv"
    csv_path = DATABASE_UPLOAD_FOLDER / f"temp_{uuid.uuid4().hex[:4]}_{filename}"
    file.save(csv_path)

    try:
        # Step 1: Read the CSV rows to inspect headers
        with csv_path.open(newline="", encoding="utf-8-sig") as csv_file:
            reader = csv.reader(csv_file)
            all_rows = list(reader)

        headers = []
        header_row_index = None

        for i, row in enumerate(all_rows):
            normalized_cells = [str(cell).strip().upper() for cell in row]
            if "ROLL NO" in normalized_cells or "NAME" in normalized_cells or "HTNO" in normalized_cells:
                headers = [str(cell).strip() for cell in row if str(cell).strip()]
                header_row_index = i
                break

        if not headers or header_row_index is None:
            headers = [str(cell).strip() for cell in all_rows if str(cell).strip()]
            header_row_index = 0

        # Step 2: Test if this is your standard college format. If yes, process it instantly!
        upper_headers = [h.upper() for h in headers]
        if "ROLL NO" in upper_headers and "NAME" in upper_headers and "PC NO" in upper_headers:
            # Create an automatic runtime mapping dictionary that your updated engine understands
            auto_mapping = {
                "student_name": headers[upper_headers.index("NAME")],
                "roll_no": headers[upper_headers.index("ROLL NO")],
                "certificate_id": headers[upper_headers.index("PC NO")],
                "cgpa": headers[upper_headers.index("CGPA")] if "CGPA" in upper_headers else ""
            }
            
            processed_rows = import_csv(
                csv_path=csv_path,
                db_path=None,
                replace=False,
                runtime_mapping=auto_mapping
            )
            
            if csv_path.exists():
                csv_path.unlink()
                
            flash(f"Database imported successfully using auto-detection! {processed_rows} record(s) processed.", "success")
            return redirect(url_for("dashboard"))

        # Step 3: Fallback path if it's an unfamiliar layout from a different college
        return render_template(
            "map_columns.html", 
            headers=headers, 
            file_path=str(csv_path.as_posix())
        )
        
    except Exception as e:
        if csv_path.exists():
            csv_path.unlink()
        print("IMPORT ENGINE EXCEPTION:", e)
        flash(f"Data Schema ingestion failed: {e}", "error")
        return redirect(url_for("dashboard"))


@app.route("/process_mapping", methods=["POST"])
def process_mapping():
    """Step 2: Collect UI mapping configurations and execute dynamic record matching ingestion."""
    file_path_str = request.form.get("file_path")
    if not file_path_str:
        flash("Invalid structural token trace recorded.", "error")
        return redirect(url_for("dashboard"))

    csv_path = Path(file_path_str)
    if not csv_path.exists():
        flash("The targeted CSV upload could not be located on the server storage layer.", "error")
        return redirect(url_for("dashboard"))

    runtime_mapping = {
        "student_name": request.form.get("name_select"),
        "roll_no": request.form.get("roll_no_select"),
        "certificate_id": request.form.get("cert_id_select"),
        "course": request.form.get("course_select") or "",
        "branch": request.form.get("branch_select") or "",
        "cgpa": request.form.get("cgpa_select") or ""
    }

    print("\n========== ACTIVE RUNTIME MAPPING CONFIG ==========")
    print(runtime_mapping)
    print("===================================================\n")

    try:
        processed_rows = import_csv(
            csv_path=csv_path,
            db_path=None,
            replace=False,
            runtime_mapping=runtime_mapping
        )
        flash(f"Universal Column Mapping Complete! Successfully processed {processed_rows} records.", "success")
    except Exception as e:
        print("DYNAMIC INGESTION RUNTIME ERROR:", e)
        flash(f"Data Schema ingestion failed: {e}", "error")
    finally:
        if csv_path.exists():
            csv_path.unlink()
            
    return redirect(url_for("dashboard"))

@app.route('/admin/login')
def safety_login_redirect():
    """
    Failsafe Node: Intercepts background browser loop requests 
    and redirects them cleanly to the dashboard instead of a 404 crash.
    """
    return redirect(url_for('dashboard'))
# --- DEDICATED PLATFORM LINKS NAVIGATION ENDPOINTS ---

@app.route('/how-to-use')
def info_how_to_use():
    """Renders the dedicated procedural workflow instructional view."""
    return render_template('how_to_use.html')

@app.route('/features')
def info_features():
    """Renders the comprehensive engineering capabilities presentation view."""
    return render_template('features.html')

@app.route('/industry')
def info_industry():
    """Renders the sector operational deployment tracking view."""
    return render_template('industry.html')

@app.route('/support')
def info_support():
    """Renders the centralized administrative help desk documentation view."""
    return render_template('support.html')

if __name__ == "__main__":
    app.run(debug=True, port=5000)
