"""Local web interface for the existing Waste Collection Management project."""

import logging
import hmac
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

from flask import Flask, Response, flash, redirect, render_template, request, send_from_directory, url_for
from werkzeug.exceptions import HTTPException

WEBSITE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = WEBSITE_DIR.parent / "Waste-Collection-Management"
ANALYTICS_DIR = Path(os.getenv("ANALYTICS_DIR", WEBSITE_DIR / "python-analysis"))
if not ANALYTICS_DIR.is_dir():
    ANALYTICS_DIR = PROJECT_DIR / "python-analysis"
sys.path.insert(0, str(ANALYTICS_DIR))

from dotenv import load_dotenv

load_dotenv(ANALYTICS_DIR / ".env")
load_dotenv(PROJECT_DIR / "python-analysis" / ".env")

from db_connection import get_connection

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY") or os.urandom(32)
app.logger.setLevel(logging.INFO)


@app.context_processor
def shared_template_values():
    return {"today_label": date.today().strftime("%A, %B %d, %Y")}


@app.before_request
def require_deployment_auth():
    if request.endpoint == "health":
        return None

    username = os.getenv("ADMIN_USERNAME")
    password = os.getenv("ADMIN_PASSWORD")
    if not username or not password:
        if os.getenv("RENDER"):
            return "Website admin credentials are not configured.", 503
        return None

    auth = request.authorization
    valid_username = auth and hmac.compare_digest(auth.username or "", username)
    valid_password = auth and hmac.compare_digest(auth.password or "", password)
    if not (valid_username and valid_password):
        return Response(
            "Authentication required.",
            401,
            {"WWW-Authenticate": 'Basic realm="WasteWise", charset="UTF-8"'},
        )
    return None


@app.get("/health")
def health():
    return {"status": "ok"}


def query(sql, params=(), one=False):
    connection = get_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute(sql, params)
        return cursor.fetchone() if one else cursor.fetchall()
    finally:
        cursor.close()
        connection.close()


def transaction(operation):
    connection = get_connection()
    cursor = connection.cursor()
    try:
        result = operation(cursor)
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        cursor.close()
        connection.close()


def required_text(field, label, limit):
    value = request.form.get(field, "").strip()
    if not value or len(value) > limit:
        raise ValueError(f"{label} is required and must be at most {limit} characters.")
    return value


def positive_int(field, label):
    try:
        value = int(request.form.get(field, ""))
    except ValueError as exc:
        raise ValueError(f"{label} must be a positive whole number.") from exc
    if value <= 0:
        raise ValueError(f"{label} must be a positive whole number.")
    return value


def positive_float(field, label):
    try:
        value = float(request.form.get(field, ""))
    except ValueError as exc:
        raise ValueError(f"{label} must be a positive number.") from exc
    if not 0 < value <= 100000000:
        raise ValueError(f"{label} must be greater than zero.")
    return value


def report_error(message, exc=None):
    if exc:
        app.logger.exception("%s", message)
    else:
        app.logger.warning("%s", message)
    flash(message, "error")


@app.errorhandler(Exception)
def handle_unexpected_error(exc):
    if isinstance(exc, HTTPException):
        return exc
    app.logger.exception("Website request failed")
    return render_template("error.html"), 500


@app.get("/")
def dashboard():
    totals = query(
        """SELECT
             (SELECT COUNT(*) FROM area) AS areas,
             (SELECT COUNT(*) FROM vehicle) AS vehicles,
             (SELECT COUNT(*) FROM collection) AS collections,
             (SELECT COALESCE(SUM(total_weight_kg),0) FROM collection
              WHERE status='Completed') AS waste_kg""",
        one=True,
    )
    statuses = query("SELECT status, COUNT(*) AS count FROM collection GROUP BY status")
    top_areas = query(
        "SELECT area_name, total_waste_kg, completed_collections "
        "FROM area_collection_report ORDER BY total_waste_kg DESC LIMIT 5"
    )
    charts = sorted(p.name for p in (ANALYTICS_DIR / "visualizations").glob("chart*.png"))
    return render_template("dashboard.html", totals=totals, statuses=statuses,
                           top_areas=top_areas, charts=charts)


@app.get("/areas")
def areas():
    return render_template("areas.html", areas=query("SELECT * FROM area ORDER BY area_name"))


@app.route("/areas/new", methods=["GET", "POST"])
def area_new():
    if request.method == "POST":
        try:
            values = (
                required_text("area_name", "Area name", 100),
                required_text("zone", "Zone", 50),
                positive_int("population", "Population"),
                required_text("contact_officer", "Contact officer", 100),
            )
            transaction(lambda cur: cur.execute(
                "INSERT INTO area (area_name,zone,population,contact_officer) VALUES (%s,%s,%s,%s)",
                values,
            ))
            flash("Area added.", "success")
            return redirect(url_for("areas"))
        except ValueError as exc:
            report_error(str(exc))
        except Exception as exc:
            report_error("Could not add area. Check that the name is unique and the database is available.", exc)
    return render_template("area_form.html", item=None)


@app.route("/areas/<int:item_id>/edit", methods=["GET", "POST"])
def area_edit(item_id):
    item = query("SELECT * FROM area WHERE area_id=%s", (item_id,), one=True)
    if not item:
        return render_template("not_found.html"), 404
    if request.method == "POST":
        try:
            values = (
                required_text("area_name", "Area name", 100),
                required_text("zone", "Zone", 50),
                positive_int("population", "Population"),
                required_text("contact_officer", "Contact officer", 100),
                item_id,
            )
            transaction(lambda cur: cur.execute(
                "UPDATE area SET area_name=%s,zone=%s,population=%s,contact_officer=%s WHERE area_id=%s",
                values,
            ))
            flash("Area updated.", "success")
            return redirect(url_for("areas"))
        except ValueError as exc:
            report_error(str(exc))
        except Exception as exc:
            report_error("Could not update area. Check that the area name is unique.", exc)
    return render_template("area_form.html", item=item)


@app.post("/areas/<int:item_id>/delete")
def area_delete(item_id):
    try:
        def delete(cur):
            cur.execute("SELECT COUNT(*) FROM collection WHERE area_id=%s AND status IN ('Scheduled','In Progress')", (item_id,))
            if cur.fetchone()[0]:
                raise ValueError("Area has pending collections and cannot be deleted.")
            cur.execute("DELETE FROM area WHERE area_id=%s", (item_id,))
            if not cur.rowcount:
                raise ValueError("Area not found.")
        transaction(delete)
        flash("Area deleted.", "success")
    except ValueError as exc:
        report_error(str(exc))
    except Exception as exc:
        report_error("Could not delete the area because it may have collection history.", exc)
    return redirect(url_for("areas"))


@app.get("/vehicles")
def vehicles():
    return render_template("vehicles.html", vehicles=query("SELECT * FROM vehicle ORDER BY registration_number"))


@app.route("/vehicles/new", methods=["GET", "POST"])
def vehicle_new():
    if request.method == "POST":
        try:
            status = request.form.get("status", "")
            if status not in {"Active", "Maintenance", "Retired"}:
                raise ValueError("Choose a valid vehicle status.")
            values = (
                required_text("registration_number", "Registration number", 20),
                required_text("vehicle_type", "Vehicle type", 50),
                positive_float("capacity_kg", "Capacity"),
                status,
            )
            transaction(lambda cur: cur.execute(
                "INSERT INTO vehicle (registration_number,vehicle_type,capacity_kg,status) VALUES (%s,%s,%s,%s)",
                values,
            ))
            flash("Vehicle added.", "success")
            return redirect(url_for("vehicles"))
        except ValueError as exc:
            report_error(str(exc))
        except Exception as exc:
            report_error("Could not add vehicle. Check that its registration is unique.", exc)
    return render_template("vehicle_form.html", item=None)


@app.route("/vehicles/<int:item_id>/edit", methods=["GET", "POST"])
def vehicle_edit(item_id):
    item = query("SELECT * FROM vehicle WHERE vehicle_id=%s", (item_id,), one=True)
    if not item:
        return render_template("not_found.html"), 404
    if request.method == "POST":
        try:
            status = request.form.get("status", "")
            if status not in {"Active", "Maintenance", "Retired"}:
                raise ValueError("Choose a valid vehicle status.")
            values = (
                required_text("registration_number", "Registration number", 20),
                required_text("vehicle_type", "Vehicle type", 50),
                positive_float("capacity_kg", "Capacity"),
                status,
                item_id,
            )
            transaction(lambda cur: cur.execute(
                "UPDATE vehicle SET registration_number=%s,vehicle_type=%s,capacity_kg=%s,status=%s WHERE vehicle_id=%s",
                values,
            ))
            flash("Vehicle updated.", "success")
            return redirect(url_for("vehicles"))
        except ValueError as exc:
            report_error(str(exc))
        except Exception as exc:
            report_error("Could not update vehicle. Check that its registration is unique.", exc)
    return render_template("vehicle_form.html", item=item)


@app.post("/vehicles/<int:item_id>/delete")
def vehicle_delete(item_id):
    try:
        def delete(cur):
            cur.execute("SELECT COUNT(*) FROM collection WHERE vehicle_id=%s AND status IN ('Scheduled','In Progress')", (item_id,))
            if cur.fetchone()[0]:
                raise ValueError("Vehicle has pending assignments and cannot be deleted.")
            cur.execute("DELETE FROM vehicle WHERE vehicle_id=%s", (item_id,))
            if not cur.rowcount:
                raise ValueError("Vehicle not found.")
        transaction(delete)
        flash("Vehicle deleted.", "success")
    except ValueError as exc:
        report_error(str(exc))
    except Exception as exc:
        report_error("Could not delete the vehicle because it may have collection history.", exc)
    return redirect(url_for("vehicles"))


@app.get("/collections")
def collections():
    rows = query(
        """SELECT c.collection_id,a.area_name,v.registration_number,c.scheduled_date,
                  c.status,c.total_weight_kg
           FROM collection c JOIN area a ON a.area_id=c.area_id
           LEFT JOIN vehicle v ON v.vehicle_id=c.vehicle_id
           ORDER BY c.scheduled_date DESC,c.collection_id DESC"""
    )
    return render_template("collections.html", rows=rows)


@app.route("/collections/new", methods=["GET", "POST"])
def collection_new():
    area_rows = query("SELECT area_id,area_name FROM area ORDER BY area_name")
    vehicle_rows = query("SELECT vehicle_id,registration_number,capacity_kg FROM vehicle WHERE status='Active' ORDER BY registration_number")
    if request.method == "POST":
        try:
            area_id = int(request.form.get("area_id", ""))
            scheduled = date.fromisoformat(request.form.get("scheduled_date", ""))
            if scheduled < date.today():
                raise ValueError("Scheduled date cannot be in the past.")
            vehicle_value = request.form.get("vehicle_id", "").strip()
            vehicle_id = int(vehicle_value) if vehicle_value else None
            def create(cur):
                cur.execute("SELECT area_id FROM area WHERE area_id=%s", (area_id,))
                if cur.fetchone() is None:
                    raise ValueError("Select a valid residential area.")
                if vehicle_id is not None:
                    cur.execute("SELECT status FROM vehicle WHERE vehicle_id=%s", (vehicle_id,))
                    vehicle = cur.fetchone()
                    if vehicle is None or vehicle[0] != "Active":
                        raise ValueError("Select an active vehicle.")
                    cur.execute(
                        "SELECT COUNT(*) FROM collection WHERE vehicle_id=%s AND scheduled_date=%s AND status IN ('Scheduled','In Progress')",
                        (vehicle_id, scheduled),
                    )
                    if cur.fetchone()[0]:
                        raise ValueError("Vehicle already has a pending collection on that date.")
                cur.execute(
                    "INSERT INTO collection (area_id,vehicle_id,scheduled_date,status) VALUES (%s,%s,%s,'Scheduled')",
                    (area_id, vehicle_id, scheduled),
                )
            transaction(create)
            flash("Collection scheduled.", "success")
            return redirect(url_for("collections"))
        except (ValueError, TypeError) as exc:
            report_error(str(exc) if str(exc) else "Select an area and valid date.")
        except Exception as exc:
            report_error("Could not schedule collection. Verify the selected area and database.", exc)
    return render_template("collection_form.html", areas=area_rows, vehicles=vehicle_rows, today=date.today().isoformat())


@app.post("/collections/<int:item_id>/status")
def collection_status(item_id):
    target = request.form.get("status", "")
    try:
        def update(cur):
            cur.execute("SELECT status,vehicle_id FROM collection WHERE collection_id=%s FOR UPDATE", (item_id,))
            item = cur.fetchone()
            if not item:
                raise ValueError("Collection not found.")
            current, vehicle_id = item
            allowed = {"Scheduled": {"In Progress", "Missed"}, "In Progress": {"Completed"}}
            if target not in allowed.get(current, set()):
                raise ValueError(f"Status change from {current} to {target} is not allowed.")
            if target == "Completed":
                if vehicle_id is None:
                    raise ValueError("Assign a vehicle before completing the collection.")
                values = []
                total = 0.0
                for category_id in (1, 2, 3):
                    try:
                        quantity = float(request.form.get(f"category_{category_id}", "0"))
                    except ValueError as exc:
                        raise ValueError("Enter valid waste quantities.") from exc
                    if quantity < 0:
                        raise ValueError("Waste quantities cannot be negative.")
                    values.append((category_id, quantity))
                    total += quantity
                cur.execute("SELECT capacity_kg FROM vehicle WHERE vehicle_id=%s", (vehicle_id,))
                capacity = cur.fetchone()
                if capacity is None or total > float(capacity[0]):
                    raise ValueError("Waste total exceeds vehicle capacity.")
                for category_id, quantity in values:
                    cur.execute(
                        "INSERT INTO collection_detail (collection_id,category_id,quantity_kg) VALUES (%s,%s,%s)",
                        (item_id, category_id, quantity),
                    )
                cur.execute(
                    "UPDATE collection SET status='Completed',actual_date=%s,total_weight_kg=%s WHERE collection_id=%s",
                    (date.today(), total, item_id),
                )
            else:
                cur.execute("UPDATE collection SET status=%s WHERE collection_id=%s", (target, item_id))
        transaction(update)
        flash("Collection status updated.", "success")
    except ValueError as exc:
        report_error(str(exc))
    except Exception as exc:
        report_error("Could not update collection. Check the category data and database.", exc)
    return redirect(url_for("collections"))


@app.get("/reports")
def reports():
    return render_template(
        "reports.html",
        areas=query("SELECT * FROM area_collection_report ORDER BY total_waste_kg DESC"),
        vehicles=query("SELECT * FROM vehicle_utilization_report ORDER BY avg_load_pct DESC"),
        completion=query("SELECT * FROM collection_completion_report", one=True),
    )


@app.get("/analytics")
def analytics():
    charts = sorted(p.name for p in (ANALYTICS_DIR / "visualizations").glob("chart*.png"))
    return render_template("analytics.html", charts=charts)


@app.post("/analytics/refresh")
def refresh_analytics():
    try:
        result = subprocess.run(
            [sys.executable, str(ANALYTICS_DIR / "visualize.py")],
            cwd=ANALYTICS_DIR, check=True, capture_output=True, text=True, timeout=180,
        )
        app.logger.info("Analytics refreshed: %s", result.stdout.strip())
        flash("Charts refreshed from MySQL.", "success")
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        app.logger.exception("Chart refresh failed")
        flash("Could not refresh charts. See the website terminal for details.", "error")
    return redirect(url_for("analytics"))


@app.get("/charts/<path:filename>")
def chart_file(filename):
    return send_from_directory(ANALYTICS_DIR / "visualizations", filename)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=False)
