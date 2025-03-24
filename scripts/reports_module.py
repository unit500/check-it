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

# Import our Plotly pie chart function from charts_module.py
import charts_module

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

    def load_template(self):
        """Load the external HTML template from the templates directory."""
        template_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "templates", "report_template.html")
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                template_content = f.read()
            return Template(template_content)
        except Exception as e:
            logging.error("Failed to load template from %s: %s", template_path, e)
            raise

    def check_and_update_schema(self, db_file):
        """
        Ensure that the 'scans' table in the given database has the required columns:
        - details_path (TEXT)
        - generated_report (TEXT), default 'no'
        - archived (INTEGER), default 0
        """
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
        """
        Fetch latest active scan results from data.db.
        Active scans are defined as those with finished = 0.
        """
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
        """
        Fetch the latest 10 completed scans from archive.db that haven't been archived yet (archived=0).
        """
        results = []
        try:
            conn = sqlite3.connect(self.archive_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, start_time, status, domain, total_scans, successful_scans, failed_scans, 
                       last_scan_time, details, duration, details_path
                FROM scans
                WHERE archived = 0
                ORDER BY last_scan_time DESC
                LIMIT 10
            """)
            results = cursor.fetchall()
            conn.close()
        except Exception as e:
            logging.error("Failed to fetch latest completed scans: %s", e)
        return results

    def calculate_progress(self, start_time, duration):
        """Calculate progress as a percentage based on start time and duration."""
        try:
            start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            elapsed = (now - start_dt).total_seconds() / 3600  # in hours
            progress = min(round((elapsed / duration) * 100, 2), 100) if duration > 0 else 100
            return f"{progress}%"
        except Exception:
            return "N/A"

    def fetch_timeline_data_from_checkhost(self):
        """
        Fetch timeline data from checkhost.db's scan_meta table.
        """
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
        """
        Generate a timeline chart as a PNG image using Plotly Express.
        """
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
        """Generate an HTML file (details.html) in the given directory with scan details and images."""
        try:
            template = self.load_template()
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
                details=report_summary.get("details"),
                details_directory=report_summary.get("details_directory"),
                extra_json_files=report_summary.get("extra_json_files")
            )
            details_html_path = os.path.join(dir_path, "details.html")
            with open(details_html_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            logging.info("Details HTML generated at %s", details_html_path)
        except Exception as e:
            logging.error("Failed to generate details HTML: %s", e)
    
    def update_details_path_in_db(self, record_id, relative_path, db_file):
        """Update the scans record with details_path and mark generated_report='yes'."""
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
        """Mark a completed scan record in the archive DB as archived (set archived = 1)."""
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
        """
        Create the details directory for an active scan, store timeline/pie charts, 
        save report JSON, and update the DB with the relative path.
        """
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
        
        relative_path = dir_path if not dir_path.startswith("/tmp/") else dir_path[len("/tmp/"):]
        
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
            "extra_json_files": []  # No extra JSON files for active scans
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
        """
        Reuse the existing details directory for a completed scan (archived scan), 
        store timeline/pie charts and update the report JSON,
        copy checkhost export JSON files (from "checkhost_exports") into the same directory,
        call export_and_remove_domain_data() to remove data from checkhost.db,
        and then mark archived=1 in archive.db.
        """
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
        
        timeline_png_path = os.path.join(dir_path, "timeline.png")
        pie_chart_path = os.path.join(dir_path, "pie_chart.png")
        json_path = os.path.join(dir_path, "report.json")
        uniq_id_path = os.path.join(dir_path, "uniq_id.txt")

        if not os.path.exists(timeline_png_path):
            self.generate_timeline_png(domain, timeline_data, timeline_png_path)
        else:
            logging.info("Timeline PNG already exists for completed scan %s", domain)
        
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
        
        relative_path = dir_path if not dir_path.startswith("/tmp/") else dir_path[len("/tmp/"):]
        
        # Copy any checkhost export JSON files from "checkhost_exports" into this directory
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

        # Export and remove checkhost data for this domain
        checkhost_client = CheckHostClient(debug=self.debug)
        checkhost_json_path = os.path.join(dir_path, f"{domain}-checkhost.json")
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
            "extra_json_files": extra_files
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
        
        if not os.path.exists(os.path.join(dir_path, "details.html")):
            self.generate_details_html(dir_path, report_summary)
        else:
            logging.info("Details HTML already exists for completed scan %s", domain)
        
        # Mark this completed scan as archived so it won't be processed again.
        self.mark_completed_as_archived(unique_id)

    def commit_changes(self, commit_message="Update generated reports and details"):
        """
        Commit and push only the details/ directory to the target Git repository.
        """
        logging.info("Attempting to commit changes with commit_message='%s'", commit_message)
        logging.info("Checking environment variables for GITHUB_OWNER, GITHUB_TOKEN, GITHUB_REPO2.")
        env_owner = os.environ.get("GITHUB_OWNER")
        env_token = os.environ.get("GITHUB_TOKEN")
        env_repo2 = os.environ.get("GITHUB_REPO2")
        if not env_owner:
            logging.warning("Environment variable GITHUB_OWNER is missing.")
        if not env_token:
            logging.warning("Environment variable GITHUB_TOKEN is missing.")
        if not env_repo2:
            logging.warning("Environment variable GITHUB_REPO2 is missing.")
        
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
            
            result = subprocess.run(["git", "remote"], capture_output=True, text=True, check=True)
            remotes = result.stdout.split()
            logging.info("Existing remotes in details repo: %s", remotes)
            
            if not env_owner or not env_token:
                logging.error("Missing GITHUB_OWNER or GITHUB_TOKEN environment variables. Aborting commit.")
                return
            
            repo_url = f"https://{env_token}@github.com/{env_owner}/{env_repo2}.git"
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
        """
        Generate an HTML report for active and completed scans,
        store scan details for both active and completed scans,
        generate the main report using the external template,
        and commit changes (only the details/ directory) back to Git.
        """
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
        
        template = self.load_template()
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
