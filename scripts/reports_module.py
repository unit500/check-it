# Version 1.3.12
import sqlite3
import logging
import os
import json
import subprocess
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
        # Use /tmp/details as the default details directory.
        self.details_dir = details_dir if details_dir else os.path.join("/tmp", "details")
    
    def check_and_update_schema(self, db_file):
        """
        Ensure that the 'scans' table in the given database has the required columns:
        - details_path (TEXT)
        - generated_report (TEXT), default 'no'
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
            conn.commit()
            conn.close()
        except Exception as e:
            logging.error("Failed to update schema for %s: %s", db_file, e)

    def fetch_latest_results(self):
        """Fetch latest active scan results from data.db that haven't been generated yet.
        Now also selects the details_path column.
        """
        results = []
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, start_time, status, domain, total_scans, successful_scans, failed_scans, last_scan_time, details, duration, details_path 
                FROM scans
                WHERE finished = 0 AND (generated_report IS NULL OR generated_report = 'no')
                ORDER BY last_scan_time DESC
            """)
            results = cursor.fetchall()
            conn.close()
        except Exception as e:
            logging.error("Failed to fetch latest results: %s", e)
        return results

    def fetch_latest_completed_scans(self):
        """Fetch latest 10 completed scans from archive.db that haven't been generated yet.
        Also selects the details_path column.
        """
        results = []
        try:
            conn = sqlite3.connect(self.archive_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, start_time, status, domain, total_scans, successful_scans, failed_scans, last_scan_time, details, duration, details_path 
                FROM scans
                WHERE (generated_report IS NULL OR generated_report = 'no')
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
        Expects the table 'scan_meta' to have columns:
            domain, first_scan, last_scan, summary_up, summary_down.
        Returns a list of dictionaries with keys: host, status, start, end.
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
        The chart is built as a Gantt-style timeline using the provided timeline_data.
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
        """Generate an HTML file (details.html) in the given directory with scan details and images.
        
        The HTML is styled with the hacker theme similar to your index page.
        """
        details_template = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8" />
          <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
          <title>Details for {{ domain }} | Check-It</title>
          <style>
            :root {
              --hacker-background: #121212;
              --hacker-card: #222222;
              --hacker-accent: #00FF41;
              --hacker-secondary: #2E8B57;
              --hacker-muted: #555555;
              --hacker-border: #333333;
              --hacker-text: #E0E0E0;
              --hacker-error: #FF0000;
            }
            body {
              margin: 0;
              padding: 0;
              font-family: "Consolas", "Monaco", "Courier New", monospace;
              background-color: var(--hacker-background);
              color: var(--hacker-text);
              line-height: 1.5;
              min-height: 100vh;
              display: flex;
              flex-direction: column;
            }
            .container {
              width: 100%;
              max-width: 1200px;
              margin: 0 auto;
              padding: 1rem;
            }
            header {
              background-color: var(--hacker-card);
              border-bottom: 1px solid rgba(0, 255, 65, 0.3);
              padding: 1rem 0;
              text-align: center;
            }
            header h1 {
              font-size: 2rem;
              color: var(--hacker-accent);
              margin: 0;
            }
            table {
              width: 100%;
              border-collapse: collapse;
              margin-top: 1rem;
            }
            table, th, td {
              border: 1px solid var(--hacker-border);
            }
            th, td {
              padding: 0.5rem;
              text-align: left;
            }
            img {
              max-width: 100%;
              height: auto;
              display: block;
              margin: 1rem 0;
            }
          </style>
        </head>
        <body>
          <header>
            <h1>Details for {{ domain }}</h1>
          </header>
          <div class="container">
            <h2>Scan Summary</h2>
            <table>
              <tr><th>Unique ID</th><td>{{ unique_id }}</td></tr>
              <tr><th>Start Time</th><td>{{ start_time }}</td></tr>
              <tr><th>Status</th><td>{{ status }}</td></tr>
              <tr><th>Total Scans</th><td>{{ total_scans }}</td></tr>
              <tr><th>Successful Scans</th><td>{{ successful_scans }}</td></tr>
              <tr><th>Failed Scans</th><td>{{ failed_scans }}</td></tr>
              <tr><th>Last Scan Time</th><td>{{ last_scan_time }}</td></tr>
              <tr><th>Duration</th><td>{{ duration }}</td></tr>
              <tr><th>Progress</th><td>{{ progress }}</td></tr>
              <tr><th>Details</th><td>{{ details }}</td></tr>
              <tr><th>Details Directory</th><td>{{ details_directory }}</td></tr>
            </table>
            <h2>Timeline Image</h2>
            <img src="timeline.png" alt="Timeline for {{ domain }}">
            <h2>Up/Down Pie Chart</h2>
            <img src="pie_chart.png" alt="Up vs Down Pie Chart for {{ domain }}">
          </div>
        </body>
        </html>
        """
        template = Template(details_template)
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
            details_directory=report_summary.get("details_directory")
        )
        details_html_path = os.path.join(dir_path, "details.html")
        with open(details_html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        logging.info("Details HTML generated at %s", details_html_path)
    
    def update_details_path_in_db(self, record_id, relative_path, db_file):
        """
        Update the scans record in the given database with the relative details directory
        and mark generated_report as 'yes'.
        """
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute("UPDATE scans SET details_path = ?, generated_report = 'yes' WHERE id = ?", (relative_path, record_id))
            conn.commit()
            conn.close()
            logging.info("Updated details_path and generated_report for record %s in %s", record_id, db_file)
        except Exception as e:
            logging.error("Failed to update details_path for record %s in %s: %s", record_id, db_file, e)
    
    def store_scan_details(self, scan_record, timeline_data):
        """
        For a given scan record, create a working directory in the format:
        /tmp/details/<year>/<month>/<day>/<domain>/
        and store:
          - timeline.png: generated PNG image of the timeline (via Plotly, using data from checkhost.db)
          - pie_chart.png: generated pie chart image showing Up vs Down percentages
          - report.json: JSON file with summary of the scan
          - uniq_id.txt: file with unique id value
          - details.html: an HTML page with all important information and images
        Additionally, update the database record with the relative details directory path (excluding the /tmp/ prefix)
        and mark generated_report as 'yes'.
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
        
        # Compute the relative details path (remove the /tmp/ prefix)
        relative_path = dir_path
        if relative_path.startswith("/tmp/"):
            relative_path = relative_path[len("/tmp/"):]
        
        report_summary = {
            "unique_id": unique_id,
            "start_time": scan_record[1],
            "status": scan_record[2],
            "domain": scan_record[3],
            "total_scans": scan_record[4],
            "successful_scans": scan_record[5],
            "failed_scans": scan_record[6],
            "last_scan_time": scan_record[7],
            "details": scan_record[8],
            "duration": scan_record[9],
            "progress": scan_record[10],
            "timeline": timeline_data,
            "details_directory": relative_path
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report_summary, f, indent=4)
        logging.info("Report JSON saved at %s", json_path)
        
        with open(uniq_id_path, "w", encoding="utf-8") as f:
            f.write(str(unique_id))
        logging.info("Unique ID saved at %s", uniq_id_path)
        
        self.generate_details_html(dir_path, report_summary)
        
        self.update_details_path_in_db(unique_id, relative_path, self.db_path)
    
    def commit_changes(self, commit_message="Update generated reports and details"):
        """
        Commit and push only the details/ directory (located in /tmp/details) to the target Git repository.
        This method changes the current working directory to self.details_dir, initializes a git repo there if needed,
        and then commits and force pushes the changes.
        """
        try:
            os.chdir(self.details_dir)
            if not os.path.exists(os.path.join(self.details_dir, ".git")):
                subprocess.run(["git", "init"], check=True)
            result = subprocess.run(["git", "remote"], capture_output=True, text=True, check=True)
            remotes = result.stdout.split()
            github_owner = os.environ.get("GITHUB_OWNER")
            github_token = os.environ.get("GITHUB_TOKEN")
            github_repo = os.environ.get("GITHUB_REPO2", "check-it-files")
            if not github_owner or not github_token:
                logging.error("Missing GITHUB_OWNER or GITHUB_TOKEN environment variables.")
                return
            repo_url = f"https://{github_token}@github.com/{github_owner}/{github_repo}.git"
            if "origin" in remotes:
                subprocess.run(["git", "remote", "set-url", "origin", repo_url], check=True)
            else:
                subprocess.run(["git", "remote", "add", "origin", repo_url], check=True)
            if os.path.exists(os.path.join(self.details_dir, ".github")):
                subprocess.run(["git", "reset", ".github"], check=True)
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", commit_message], check=True)
            subprocess.run(["git", "push", "--force", "origin", "master"], check=True)
            logging.info("Details directory committed and force pushed successfully from %s.", self.details_dir)
        except subprocess.CalledProcessError as e:
            logging.error("Failed to commit changes: %s", e)
    
    def generate(self):
        """Generate an HTML report for active and completed scans,
        store working files for each active scan, generate the main report,
        and commit changes (only the details/ directory) back to Git.
        """
        self.check_and_update_schema(self.db_path)
        self.check_and_update_schema(self.archive_path)
        
        active_scans = self.fetch_latest_results()
        completed_scans = self.fetch_latest_completed_scans()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        timeline_data_all = self.fetch_timeline_data_from_checkhost()
        timeline_data_json = json.dumps(timeline_data_all)
        
        # Each active scan row now has 11 elements (with details_path at index 10).
        active_scans_with_progress = [list(row) + [self.calculate_progress(row[1], row[9])] for row in active_scans]
        completed_scans_with_progress = [list(row) + [self.calculate_progress(row[1], row[9])] for row in completed_scans]
        
        # For each active scan, match timeline data by domain from checkhost.db.
        for scan in active_scans_with_progress:
            td = next((item for item in timeline_data_all if item["host"] == scan[3]), None)
            self.store_scan_details(scan, td)
        
        HTML_TEMPLATE = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Reports | Check-It Uptime Monitoring</title>
            <script src="https://cdn.tailwindcss.com"></script>
            <!-- ECharts CDN -->
            <script src="https://cdn.jsdelivr.net/npm/echarts/dist/echarts.min.js"></script>
        </head>
        <body class="min-h-screen flex flex-col bg-gradient-to-b from-white to-gray-50">
            <header class="w-full bg-gradient-to-r from-blue-900 to-blue-700 text-white shadow-lg">
                <div class="container mx-auto py-6 px-4 text-center">
                    <h1 class="text-3xl font-bold tracking-tight">Check-It Uptime Monitoring</h1>
                    <p class="text-monitor-100 text-lg mt-2">Real-time server monitoring with detailed status reports.</p>
                </div>
            </header>

            <main class="flex-1">
                <div class="container mx-auto px-4 py-10">
                    <div class="max-w-6xl mx-auto bg-white shadow-md rounded-lg p-6">
                        <div class="border-b pb-4 mb-6">
                            <h3 class="text-2xl font-semibold">Monitoring Report</h3>
                            <p class="text-gray-500 text-sm">Generated on: {{ now }}</p>
                        </div>

                        <p class="text-lg font-semibold mb-4">
                            Status: 
                            {% if active_scans_with_progress %}
                                <span class="text-red-500">
                                    {{ active_scans_with_progress | selectattr('2', 'equalto', 'Down') | list | length }} out of {{ active_scans_with_progress | length }} hosts are DOWN
                                </span>
                            {% else %}
                                <span class="text-green-500">No active scans</span>
                            {% endif %}
                        </p>

                        <div class="overflow-x-auto mb-8">
                            <table class="min-w-full border border-gray-300 text-sm text-left">
                                <thead class="bg-blue-50 text-blue-900">
                                    <tr>
                                        <th class="border border-gray-300 px-4 py-2">Start Time</th>
                                        <th class="border border-gray-300 px-4 py-2">Status</th>
                                        <th class="border border-gray-300 px-4 py-2">Host</th>
                                        <th class="border border-gray-300 px-4 py-2">Progress</th>
                                        <th class="border border-gray-300 px-4 py-2">Total Scans</th>
                                        <th class="border border-gray-300 px-4 py-2">Successful Scans</th>
                                        <th class="border border-gray-300 px-4 py-2">Failed Scans</th>
                                        <th class="border border-gray-300 px-4 py-2">Last Scan Time</th>
                                        <th class="border border-gray-300 px-4 py-2">Details</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for row in active_scans_with_progress %}
                                    <tr class="border border-gray-300 {% if loop.index is even %} bg-gray-50 {% endif %}">
                                        <td class="px-4 py-2 text-gray-500">{{ row[1] }}</td>
                                        <td class="px-4 py-2 {% if row[2] == 'Up' %} text-green-600 {% else %} text-red-600 {% endif %}">{{ row[2] }}</td>
                                        <td class="px-4 py-2 font-medium">
                                          {% if row[10] %}
                                            <a href="https://unit500.github.io/check-it-files/{{ row[10] }}/details.html" target="_blank">{{ row[3] }}</a>
                                          {% else %}
                                            {{ row[3] }}
                                          {% endif %}
                                        </td>
                                        <td class="px-4 py-2 text-blue-600 font-semibold">{{ row[11] }}</td>
                                        <td class="px-4 py-2">{{ row[4] }}</td>
                                        <td class="px-4 py-2">{{ row[5] }}</td>
                                        <td class="px-4 py-2">{{ row[6] }}</td>
                                        <td class="px-4 py-2 text-gray-500">{{ row[7] }}</td>
                                        <td class="px-4 py-2 text-gray-600">{{ row[8] }}</td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>

                        <div id="timelineChart" style="height: 400px;" class="mb-8"></div>
                        <script>
                            var timelineData = {{ timeline_data_json | safe }};
                            if(timelineData.length > 0){
                                var minTime = Math.min.apply(null, timelineData.map(function(item){ return item.start; }));
                                var maxTime = Math.max.apply(null, timelineData.map(function(item){ return item.end; }));
                                var chartDom = document.getElementById('timelineChart');
                                var myChart = echarts.init(chartDom);
                                var option = {
                                    tooltip: {
                                        formatter: function(params) {
                                            var item = timelineData[params.dataIndex];
                                            return item.host + '<br/>' + 
                                                new Date(item.start).toLocaleString() + ' ~ ' + new Date(item.end).toLocaleString() + '<br/>' + 
                                                'Status: ' + item.status;
                                        }
                                    },
                                    grid: { containLabel: true },
                                    xAxis: {
                                        type: 'value',
                                        min: minTime,
                                        max: maxTime,
                                        axisLabel: {
                                            formatter: function (value) {
                                                return new Date(value).toLocaleTimeString();
                                            }
                                        }
                                    },
                                    yAxis: {
                                        type: 'category',
                                        data: timelineData.map(function(item){ return item.host; })
                                    },
                                    series: [{
                                        name: 'Start',
                                        type: 'bar',
                                        stack: 'total',
                                        itemStyle: { color: 'transparent' },
                                        emphasis: { itemStyle: { color: 'transparent' } },
                                        data: timelineData.map(function(item){ return item.start; })
                                    }, {
                                        name: 'Duration',
                                        type: 'bar',
                                        stack: 'total',
                                        label: {
                                            show: true,
                                            position: 'inside',
                                            formatter: function (params) {
                                                return timelineData[params.dataIndex].status;
                                            }
                                        },
                                        data: timelineData.map(function(item){ return item.end - item.start; }),
                                        itemStyle: {
                                            color: function (params) {
                                                var status = timelineData[params.dataIndex].status;
                                                return status === 'Up' ? '#4caf50' : '#f44336';
                                            }
                                        }
                                    }]
                                };
                                myChart.setOption(option);
                            }
                        </script>

                        <hr class="my-10 border-gray-300">
                        <h3 class="text-xl font-semibold mb-4">Latest 10 Completed Checks</h3>

                        <div class="overflow-x-auto">
                            <table class="min-w-full border border-gray-300 text-sm text-left">
                                <tbody>
                                    {% for row in completed_scans_with_progress %}
                                    <tr class="border border-gray-300 {% if loop.index is even %} bg-gray-50 {% endif %}">
                                        <td class="px-4 py-2 text-gray-500">{{ row[1] }}</td>
                                        <td class="px-4 py-2">{{ row[2] }}</td>
                                        <td class="px-4 py-2 font-medium">{{ row[3] }}</td>
                                        <td class="px-4 py-2 text-blue-600 font-semibold">{{ row[11] }}</td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </main>
        </body>
        </html>
        """
        template = Template(HTML_TEMPLATE)
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

    def commit_changes(self, commit_message="Update generated reports and details"):
        """
        Commit and push only the details/ directory (located in /tmp/details) to the target Git repository.
        This method changes the current working directory to self.details_dir, initializes a git repo there if needed,
        and then commits and force pushes the changes.
        """
        try:
            os.chdir(self.details_dir)
            if not os.path.exists(os.path.join(self.details_dir, ".git")):
                subprocess.run(["git", "init"], check=True)
            result = subprocess.run(["git", "remote"], capture_output=True, text=True, check=True)
            remotes = result.stdout.split()
            github_owner = os.environ.get("GITHUB_OWNER")
            github_token = os.environ.get("GITHUB_TOKEN")
            github_repo = os.environ.get("GITHUB_REPO2", "check-it-files")
            if not github_owner or not github_token:
                logging.error("Missing GITHUB_OWNER or GITHUB_TOKEN environment variables.")
                return
            repo_url = f"https://{github_token}@github.com/{github_owner}/{github_repo}.git"
            if "origin" in remotes:
                subprocess.run(["git", "remote", "set-url", "origin", repo_url], check=True)
            else:
                subprocess.run(["git", "remote", "add", "origin", repo_url], check=True)
            if os.path.exists(os.path.join(self.details_dir, ".github")):
                subprocess.run(["git", "reset", ".github"], check=True)
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", commit_message], check=True)
            subprocess.run(["git", "push", "--force", "origin", "master"], check=True)
            logging.info("Details directory committed and force pushed successfully from %s.", self.details_dir)
        except subprocess.CalledProcessError as e:
            logging.error("Failed to commit changes: %s", e)
