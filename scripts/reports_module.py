# reports_module.py (version 1.6)
import sqlite3
import logging
import os
import json
import subprocess
import shutil
from datetime import datetime, timedelta
from jinja2 import Template
import plotly.express as px
import pandas as pd

# --- New Imports for DDOS Map Animation and Timeline Generation from JSON ---
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import matplotlib.patches as mpatches
import matplotlib.animation as animation
import re

# Import our Plotly pie chart function from charts_module.py
import charts_module

# --- Fallback coordinates for country codes (ISO alpha-2 -> (lat, lon)) ---
fallback_coords = {
"bg": (42.7339, 25.4858),
    "br": (-14.2350, -51.9253),
    "ch": (46.8182, 8.2275),
    "cz": (49.8175, 15.4730),
    "de": (51.1657, 10.4515),
    "es": (40.4637, -3.7492),
    "fi": (61.9241, 25.7482),
    "fr": (46.2276, 2.2137),
    "hk": (22.3964, 114.1095),
    "hu": (47.1625, 19.5033),
    "id": (-0.7893, 113.9213),
    "il": (31.0461, 34.8516),
    "in": (20.5937, 78.9629),
    "ir": (32.4279, 53.6880),
    "it": (41.8719, 12.5674),
    "jp": (36.2048, 138.2529),
    "kz": (48.0196, 66.9237),
    "lt": (55.1694, 23.8813),
    "md": (47.4116, 28.3699),
    "nl": (52.1326, 5.2913),
    "pl": (51.9194, 19.1451),
    "pt": (39.3999, -8.2245),
    "rs": (44.0165, 21.0059),
    "ru": (61.5240, 105.3188),
    "se": (60.1282, 18.6435),
    "tr": (38.9637, 35.2433),
    "ua": (48.3794, 31.1656),
    "uk": (55.3781, -3.4360),
    "us": (37.0902, -95.7129),
    "vn": (14.0583, 108.2772)
}

def generate_ddos_map(check_details, attacked_country, output_filename):
    """
    Generate a static world map image using Cartopy:
      - Red circles for each unique country derived from check_details keys.
      - A black circle for the attacked country.
    Saves the image to output_filename.
    """
    results = check_details.get("check_results", {})
    red_coords = set()
    for node in results.keys():
        match = re.match(r"([a-zA-Z]+)", node)
        if match:
            code = match.group(1).lower()[:2]
            coords = fallback_coords.get(code)
            if coords:
                red_coords.add(coords)
    black_coords = None
    if attacked_country:
        try:
            import pycountry
            matches = pycountry.countries.search_fuzzy(attacked_country)
            if matches:
                country_code = matches[0].alpha_2.lower()
                black_coords = fallback_coords.get(country_code)
        except Exception as e:
            logging.error(f"Error getting coordinates for attacked country '{attacked_country}': {e}")
    fig = plt.figure(figsize=(12, 6))
    ax = plt.axes(projection=ccrs.PlateCarree())
    ax.set_global()
    ax.add_feature(cfeature.LAND, facecolor='lightgray')
    ax.add_feature(cfeature.OCEAN, facecolor='aliceblue')
    ax.add_feature(cfeature.BORDERS, linestyle='-', edgecolor='gray')
    ax.coastlines()
    if red_coords:
        lats, lons = zip(*red_coords)
        ax.scatter(lons, lats, color='red', s=100, transform=ccrs.PlateCarree(), zorder=5)
    if black_coords:
        ax.scatter([black_coords[1]], [black_coords[0]], color='black', s=150, transform=ccrs.PlateCarree(), zorder=6)
    ax.set_title("DDOS Availability Map", fontsize=16)
    red_patch = mpatches.Patch(color='red', label='Inaccessible locations')
    black_patch = mpatches.Patch(color='black', label='Targeted server')
    ax.legend(handles=[black_patch, red_patch], loc='lower left', fontsize='small')
    plt.savefig(output_filename, bbox_inches='tight', dpi=150)
    plt.close()

def generate_ddos_map_animated(check_details, attacked_country, output_filename, frames=20, interval=200):
    """
    Generate an animated DDOS map as a GIF.
    Rotates the world map by updating the central_longitude.
    """
    results = check_details.get("check_results", {})
    red_coords = set()
    for node in results.keys():
        match = re.match(r"([a-zA-Z]+)", node)
        if match:
            code = match.group(1).lower()[:2]
            coords = fallback_coords.get(code)
            if coords:
                red_coords.add(coords)
    black_coords = None
    if attacked_country:
        try:
            import pycountry
            matches = pycountry.countries.search_fuzzy(attacked_country)
            if matches:
                country_code = matches[0].alpha_2.lower()
                black_coords = fallback_coords.get(country_code)
        except Exception as e:
            logging.error(f"Error getting coordinates for attacked country '{attacked_country}': {e}")
    fig = plt.figure(figsize=(12, 6))
    ax = plt.axes(projection=ccrs.PlateCarree(central_longitude=0))
    ax.set_global()
    ax.add_feature(cfeature.LAND, facecolor='lightgray')
    ax.add_feature(cfeature.OCEAN, facecolor='aliceblue')
    ax.add_feature(cfeature.BORDERS, linestyle='-', edgecolor='gray')
    ax.coastlines()
    title = ax.set_title("DDOS Availability Map", fontsize=16)

    def update(frame):
        angle = -180 + (360.0/frames)*frame
        ax.clear()
        proj = ccrs.PlateCarree(central_longitude=angle)
        ax.set_global()
        ax.set_projection(proj)
        ax.add_feature(cfeature.LAND, facecolor='lightgray')
        ax.add_feature(cfeature.OCEAN, facecolor='aliceblue')
        ax.add_feature(cfeature.BORDERS, linestyle='-', edgecolor='gray')
        ax.coastlines()
        if red_coords:
            ax.scatter(*zip(*red_coords), color='red', s=100, transform=ccrs.PlateCarree(), zorder=5)
        if black_coords:
            ax.scatter([black_coords[1]], [black_coords[0]], color='black', s=150, transform=ccrs.PlateCarree(), zorder=6)
        ax.set_title(f"DDOS Availability Map\nCentral Longitude: {angle:.0f}°", fontsize=16)
        red_patch = mpatches.Patch(color='red', label='Inaccessible locations')
        black_patch = mpatches.Patch(color='black', label='Targeted server')
        ax.legend(handles=[black_patch, red_patch], loc='lower left', fontsize='small')

    anim = animation.FuncAnimation(fig, update, frames=frames, interval=interval)
    anim.save(output_filename, writer='pillow', dpi=150)
    plt.close()

def generate_timeline_png_from_json(json_file, output_path):
    """
    Generate a timeline chart PNG from a check-host JSON export.
    Reads the JSON file, extracts each object's first_scan and last_scan,
    and uses that to build a timeline DataFrame for plotting.
    """
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logging.error(f"Error loading JSON file {json_file}: {e}")
        return

    timeline_data = []
    domain = data.get("domain", "Unknown")
    local_ids = data.get("local_ids", [])
    for item in local_ids:
        first_scan = item.get("first_scan")
        last_scan = item.get("last_scan")
        if first_scan and last_scan:
            try:
                start_dt = datetime.strptime(first_scan, "%Y-%m-%d %H:%M:%S")
                end_dt = datetime.strptime(last_scan, "%Y-%m-%d %H:%M:%S")
            except Exception as e:
                logging.error(f"Error parsing dates in JSON for domain {domain}: {e}")
                continue
            summary_up = item.get("summary_up", 0)
            summary_down = item.get("summary_down", 0)
            status = "Up" if summary_up >= summary_down else "Down"
            timeline_data.append({
                "host": domain,
                "status": status,
                "start": int(start_dt.timestamp() * 1000),
                "end": int(end_dt.timestamp() * 1000)
            })
    
    import pandas as pd
    if not timeline_data:
        df = pd.DataFrame([], columns=["host", "status", "start", "end"])
    else:
        df = pd.DataFrame(timeline_data)
        df['start'] = pd.to_datetime(df['start'], unit='ms')
        df['end'] = pd.to_datetime(df['end'], unit='ms')
    
    fig = px.timeline(df, x_start="start", x_end="end", y="host", color="status")
    fig.update_yaxes(autorange="reversed")
    fig.write_image(output_path)
    logging.info(f"Timeline PNG generated from JSON at {output_path}")

class Reports:
    def __init__(self, db_path=None, archive_path=None, output_path=None, details_dir=None, debug=False):
        """Initialize the report generation class with database paths.
        By default, the details directory is set to '/tmp/details'.
        """
        self.debug = debug
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = db_path if db_path else os.path.join(script_dir, "..", "data", "data.db")
        self.archive_path = archive_path if archive_path else os.path.join(script_dir, "..", "data", "archive.db")
        self.output_path = output_path if output_path else os.path.join(script_dir, "..", "report.html")
        self.details_dir = details_dir if details_dir else os.path.join("/tmp", "details")
        logging.info("Reports initialized with db_path=%s, archive_path=%s, output_path=%s, details_dir=%s",
                     self.db_path, self.archive_path, self.output_path, self.details_dir)

    def fetch_scans_to_regenerate(self, days=7):
        results = []
        try:
            conn = sqlite3.connect(self.archive_path)
            cursor = conn.cursor()
            cutoff = datetime.now() - timedelta(days=days)
            cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute(f"""
                SELECT id, start_time, status, domain, total_scans, successful_scans, failed_scans,
                       last_scan_time, details, duration, details_path
                FROM scans
                WHERE last_scan_time >= ?
                ORDER BY last_scan_time DESC
            """, (cutoff_str,))
            results = cursor.fetchall()
            conn.close()
            logging.info("Fetched %d archived scans to regenerate (last %d days).", len(results), days)
        except Exception as e:
            logging.error("Failed to fetch scans to regenerate: %s", e)
        return results

    def load_template(self, template_name="report_template.html"):
        template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates", template_name)
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                template_content = f.read()
            return Template(template_content)
        except Exception as e:
            logging.error("Failed to load template from %s: %s", template_path, e)
            raise

    def check_and_update_schema(self, db_file):
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(scans)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'details_path' not in columns:
                cursor.execute("ALTER TABLE scans ADD COLUMN details_path TEXT")
                logging.info("Added 'details_path' column to %s", db_file)
            if 'generated_report' not in columns:
                cursor.execute("ALTER TABLE scans ADD COLUMN generated_report TEXT DEFAULT 'no'")
                logging.info("Added 'generated_report' column to %s", db_file)
            if 'archived' not in columns:
                cursor.execute("ALTER TABLE scans ADD COLUMN archived INTEGER DEFAULT 0")
                logging.info("Added 'archived' column to %s", db_file)
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error("Failed to update schema for %s: %s", db_file, e)

    def fetch_latest_results(self):
        results = []
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, start_time, status, domain, total_scans, successful_scans, failed_scans, 
                       last_scan_time, details, duration, details_path
                FROM scans
                WHERE finished = 0
                ORDER BY last_scan_time DESC
            """)
            results = cursor.fetchall()
            conn.close()
        except Exception as e:
            logging.error("Failed to fetch latest results: %s", e)
        return results

    def fetch_latest_completed_scans(self):
        results = []
        try:
            conn = sqlite3.connect(self.archive_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, start_time, status, domain, total_scans, successful_scans, failed_scans, 
                       last_scan_time, details, duration, details_path
                FROM scans                
                ORDER BY last_scan_time DESC
                LIMIT 10
            """)
            results = cursor.fetchall()
            conn.close()
        except Exception as e:
            logging.error("Failed to fetch latest completed scans: %s", e)
        return results

    def calculate_progress(self, start_time, duration):
        try:
            start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            elapsed = (now - start_dt).total_seconds() / 3600
            progress = min(round((elapsed / duration) * 100, 2), 100) if duration > 0 else 100
            return f"{progress}%"
        except Exception:
            return "N/A"

    def fetch_timeline_data_from_checkhost(self):
        timeline_data = []
        try:
            checkhost_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "checkhost.db")
            conn = sqlite3.connect(checkhost_db)
            cursor = conn.cursor()
            cursor.execute("SELECT domain, first_scan, last_scan, summary_up, summary_down FROM scan_meta")
            rows = cursor.fetchall()
            conn.close()
            for row in rows:
                domain, first_scan, last_scan, summary_up, summary_down = row
                if first_scan and last_scan:
                    start_dt = datetime.strptime(first_scan, "%Y-%m-%d %H:%M:%S")
                    end_dt = datetime.strptime(last_scan, "%Y-%m-%d %H:%M:%S")
                    status = "Up" if summary_up >= summary_down else "Down"
                    timeline_data.append({
                        "host": domain,
                        "status": status,
                        "start": int(start_dt.timestamp() * 1000),
                        "end": int(end_dt.timestamp() * 1000)
                    })
        except Exception as e:
            logging.error("Failed to fetch timeline data from checkhost.db: %s", e)
        return timeline_data

    def generate_timeline_png(self, domain, timeline_data, output_path):
        if timeline_data is None:
            df = pd.DataFrame([], columns=["host", "status", "start", "end"])
        else:
            if isinstance(timeline_data, dict):
                timeline_data = [timeline_data]
            df = pd.DataFrame(timeline_data)
            df['start'] = pd.to_datetime(df['start'], unit='ms')
            df['end'] = pd.to_datetime(df['end'], unit='ms')
        fig = px.timeline(df, x_start="start", x_end="end", y="host", color="status")
        fig.update_yaxes(autorange="reversed")
        fig.write_image(output_path)
        logging.info("Timeline PNG generated at %s", output_path)

    def generate_details_html(self, dir_path, report_summary):
        try:
            template = self.load_template("details_template.html")
            html_content = template.render(
                unique_id=report_summary.get("unique_id"),
                start_time=report_summary.get("start_time"),
                status=report_summary.get("status"),
                domain=report_summary.get("domain"),
                total_scans=report_summary.get("total_scans"),
                successful_scans=report_summary.get("successful_scans"),
                failed_scans=report_summary.get("failed_scans"),
                last_scan_time=report_summary.get("last_scan_time"),
                duration=report_summary.get("duration"),
                progress=report_summary.get("progress"),
                extra_json_files=report_summary.get("extra_json_files")
            )
            details_html_path = os.path.join(dir_path, "details.html")
            with open(details_html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            logging.info("Details HTML generated at %s", details_html_path)
        except Exception as e:
            logging.error("Failed to generate details HTML: %s", e)
    
    def update_details_path_in_db(self, record_id, relative_path, db_file):
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute("UPDATE scans SET details_path = ?, generated_report = 'yes' WHERE id = ?", (relative_path, record_id))
            conn.commit()
            conn.close()
            logging.info("Updated details_path and generated_report for record %s in %s", record_id, db_file)
        except Exception as e:
            logging.error("Failed to update details_path for record %s in %s: %s", record_id, db_file, e)
    
    def mark_completed_as_archived(self, record_id):
        try:
            conn = sqlite3.connect(self.archive_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE scans SET archived = 1 WHERE id = ?", (record_id,))
            conn.commit()
            conn.close()
            logging.info("Marked completed scan record %s as archived", record_id)
        except Exception as e:
            logging.error("Failed to mark record %s as archived: %s", record_id, e)

    def store_scan_details(self, scan_record, timeline_data):
        unique_id = scan_record[0]
        start_time_str = scan_record[1]
        domain = scan_record[3]
        try:
            start_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logging.error("Error parsing start time for scan %s: %s", scan_record, e)
            return
        
        dir_path = os.path.join(self.details_dir, start_dt.strftime("%Y"), start_dt.strftime("%m"), start_dt.strftime("%d"), domain)
        os.makedirs(dir_path, exist_ok=True)
        
        timeline_png_path = os.path.join(dir_path, "timeline.png")
        pie_chart_path = os.path.join(dir_path, "pie_chart.png")
        json_path = os.path.join(dir_path, "report.json")
        uniq_id_path = os.path.join(dir_path, "uniq_id.txt")
        
        # For active scans we use the DB timeline data.
        self.generate_timeline_png(domain, timeline_data, timeline_png_path)
        
        total = scan_record[4]
        successful = scan_record[5]
        failed = scan_record[6]
        if total > 0:
            up_percentage = round((successful / total) * 100, 2)
            down_percentage = round((failed / total) * 100, 2)
        else:
            up_percentage = 0
            down_percentage = 0
        
        charts_module.generate_pie_chart_plotly(up_percentage, down_percentage, pie_chart_path)
        
        relative_path = os.path.relpath(dir_path, self.details_dir)
        
        report_summary = {
            "unique_id": unique_id,
            "start_time": scan_record[1],
            "status": scan_record[2],
            "domain": domain,
            "total_scans": scan_record[4],
            "successful_scans": scan_record[5],
            "failed_scans": scan_record[6],
            "last_scan_time": scan_record[7],
            "details": scan_record[8],
            "duration": scan_record[9],
            "progress": scan_record[10],
            "extra_json_files": []
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report_summary, f, indent=4)
        logging.info("Report JSON updated at %s", json_path)
        
        if not os.path.exists(uniq_id_path):
            with open(uniq_id_path, "w", encoding="utf-8") as f:
                f.write(str(unique_id))
            logging.info("Unique ID file created at %s", uniq_id_path)
        else:
            logging.info("Unique ID file already exists for %s", domain)
        
        self.generate_details_html(dir_path, report_summary)
        self.update_details_path_in_db(unique_id, relative_path, self.db_path)

    def store_completed_scan_details(self, scan_record, timeline_data):
        from checkhost import CheckHostClient

        unique_id = scan_record[0]
        start_time_str = scan_record[1]
        domain = scan_record[3]
        try:
            start_dt = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
        except Exception as e:
            logging.error("Error parsing start time for completed scan %s: %s", scan_record, e)
            return
        
        dir_path = os.path.join(self.details_dir, start_dt.strftime("%Y"), start_dt.strftime("%m"), start_dt.strftime("%d"), domain)
        os.makedirs(dir_path, exist_ok=True)
        
        # Instead of using DB timeline data, we now want to use the exported JSON.
        timeline_png_path = os.path.join(dir_path, "timeline.png")
        pie_chart_path = os.path.join(dir_path, "pie_chart.png")
        json_path = os.path.join(dir_path, "report.json")
        uniq_id_path = os.path.join(dir_path, "uniq_id.txt")

        # For completed scans, generate timeline PNG from the exported JSON.
        checkhost_json_path = os.path.join(dir_path, f"{domain}-checkhost.json")
        exported_file = None
        checkhost_client = CheckHostClient(debug=self.debug)
        exported_file = checkhost_client.export_and_remove_domain_data(domain, checkhost_json_path)
        if exported_file:
            generate_timeline_png_from_json(exported_file, timeline_png_path)
        else:
            # Fallback: use the DB timeline data
            self.generate_timeline_png(domain, timeline_data, timeline_png_path)
        
        total = scan_record[4]
        successful = scan_record[5]
        failed = scan_record[6]
        if total > 0:
            up_percentage = round((successful / total) * 100, 2)
            down_percentage = round((failed / total) * 100, 2)
        else:
            up_percentage = 0
            down_percentage = 0
        
        if not os.path.exists(pie_chart_path):
            charts_module.generate_pie_chart_plotly(up_percentage, down_percentage, pie_chart_path)
        else:
            logging.info("Pie chart already exists for completed scan %s", domain)
        
        relative_path = os.path.relpath(dir_path, self.details_dir)
        
        source_exports = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "checkhost_exports")
        extra_files = []
        if os.path.exists(source_exports):
            for file in os.listdir(source_exports):
                if domain in file:
                    src = os.path.join(source_exports, file)
                    dst = os.path.join(dir_path, file)
                    try:
                        shutil.copy(src, dst)
                        extra_files.append(file)
                        logging.info("Copied JSON export file %s for completed scan %s", file, domain)
                    except Exception as e:
                        logging.error("Failed to copy JSON export file %s: %s", file, e)
        else:
            logging.warning("Source exports folder %s does not exist.", source_exports)

        # Attempt to export check-host data; if found, append to extra_files.
        exported_file = checkhost_client.export_and_remove_domain_data(domain, checkhost_json_path)
        if exported_file:
            extra_files.append(os.path.basename(exported_file))
        
        report_summary = {
            "unique_id": unique_id,
            "start_time": scan_record[1],
            "status": scan_record[2],
            "domain": domain,
            "total_scans": scan_record[4],
            "successful_scans": scan_record[5],
            "failed_scans": scan_record[6],
            "last_scan_time": scan_record[7],
            "details": scan_record[8],
            "duration": scan_record[9],
            "progress": scan_record[10],
            "extra_json_files": extra_files,
            "check_details": scan_record[8] if isinstance(scan_record[8], dict) else None,
            "attacked_country": scan_record[8].get("attacked_country") if isinstance(scan_record[8], dict) and "attacked_country" in scan_record[8] else ""
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report_summary, f, indent=4)
        logging.info("Report JSON updated at %s", json_path)
        
        if not os.path.exists(uniq_id_path):
            with open(uniq_id_path, "w", encoding="utf-8") as f:
                f.write(str(unique_id))
            logging.info("Unique ID file created at %s", uniq_id_path)
        else:
            logging.info("Unique ID file already exists for completed scan %s", domain)
        
        # --- DDOS Animated Map Generation Integration ---
        ddos_map_gif_path = os.path.join(dir_path, "ddos_map.gif")
        if report_summary.get("check_details"):
            generate_ddos_map_animated(report_summary["check_details"],
                                       report_summary.get("attacked_country", ""),
                                       ddos_map_gif_path)
            logging.info("Animated DDOS map generated at %s", ddos_map_gif_path)
        else:
            logging.info("No check_details available; skipping animated DDOS map generation for %s", domain)
        
        if not os.path.exists(os.path.join(dir_path, "details.html")):
            self.generate_details_html(dir_path, report_summary)
        else:
            logging.info("Details HTML already exists for completed scan %s", domain)
        
        self.mark_completed_as_archived(unique_id)

    def commit_changes(self, commit_message="Update generated reports and details"):
        logging.info("Attempting to commit changes with commit_message='%s'", commit_message)
        logging.info("Checking environment variables for OWNER, TOKEN, REPO2.")
        owner = os.environ.get("OWNER")
        token = os.environ.get("TOKEN")
        repo2 = os.environ.get("REPO2")
        if not owner:
            logging.warning("Environment variable OWNER is missing.")
        if not token:
            logging.warning("Environment variable TOKEN is missing.")
        if not repo2:
            logging.warning("Environment variable REPO2 is missing.")
        
        if not os.path.exists(self.details_dir):
            logging.warning("Details directory %s does not exist; creating it now.", self.details_dir)
            try:
                os.makedirs(self.details_dir, exist_ok=True)
            except Exception as e:
                logging.error("Failed to create details directory %s: %s", self.details_dir, e)
                return
        
        try:
            os.chdir(self.details_dir)
            logging.info("Changed directory to %s", self.details_dir)
            if not os.path.exists(os.path.join(self.details_dir, ".git")):
                logging.info("Initializing a new git repository in %s", self.details_dir)
                subprocess.run(["git", "init"], check=True)
                subprocess.run(["git", "config", "user.name", "github-actions"], check=True)
                subprocess.run(["git", "config", "user.email", "github-actions@github.com"], check=True)
    
            result = subprocess.run(["git", "remote"], capture_output=True, text=True, check=True)
            remotes = result.stdout.split()
            logging.info("Existing remotes in details repo: %s", remotes)
            
            if not owner or not token:
                logging.error("Missing OWNER or TOKEN environment variables. Aborting commit.")
                return
            
            repo_url = f"https://{token}@github.com/{owner}/{repo2}.git"
            if "origin" in remotes:
                logging.info("Setting remote origin URL to %s", repo_url)
                subprocess.run(["git", "remote", "set-url", "origin", repo_url], check=True)
            else:
                logging.info("Adding remote origin with URL %s", repo_url)
                subprocess.run(["git", "remote", "add", "origin", repo_url], check=True)
            
            if os.path.exists(os.path.join(self.details_dir, ".github")):
                logging.info(".github directory found, resetting it.")
                subprocess.run(["git", "reset", ".github"], check=True)
            else:
                logging.info(".github directory not found in %s; skipping reset.", self.details_dir)
            
            subprocess.run(["git", "add", "."], check=True)
            logging.info("Staged all files in %s", self.details_dir)
            subprocess.run(["git", "commit", "-m", commit_message], check=True)
            logging.info("Committed changes with message '%s'", commit_message)
            subprocess.run(["git", "push", "--force", "origin", "master"], check=True)
            logging.info("Force-pushed changes to origin/master.")
        except subprocess.CalledProcessError as e:
            logging.error("Failed to commit changes: %s", e)

    def generate(self):
        self.check_and_update_schema(self.db_path)
        self.check_and_update_schema(self.archive_path)
        
        active_scans = self.fetch_latest_results()
        completed_scans = self.fetch_latest_completed_scans()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        timeline_data_all = self.fetch_timeline_data_from_checkhost()
        timeline_data_json = json.dumps(timeline_data_all)
        
        active_scans_with_progress = [list(row) + [self.calculate_progress(row[1], row[9])] for row in active_scans]
        completed_scans_with_progress = [list(row) + [self.calculate_progress(row[1], row[9])] for row in completed_scans]
        
        for scan in active_scans_with_progress:
            td = next((item for item in timeline_data_all if item["host"] == scan[3]), None)
            self.store_scan_details(scan, td)
        
        for scan in completed_scans_with_progress:
            td = next((item for item in timeline_data_all if item["host"] == scan[3]), None)
            self.store_completed_scan_details(scan, td)
        
        template = self.load_template()  # loads report_template.html by default
        html_content = template.render(
            now=now,
            active_scans_with_progress=active_scans_with_progress,
            completed_scans_with_progress=completed_scans_with_progress,
            timeline_data_json=timeline_data_json
        )
        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logging.info("Main HTML report generated at %s", self.output_path)
        self.commit_changes()
