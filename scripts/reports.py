from datetime import datetime
from jinja2 import Template
import logging
import os
import sqlite3

class Reports:
    def __init__(self, debug=False):
        self.debug = debug
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.report_filename = os.path.join(script_dir, "..", "report.html")
        self.db_path = os.path.join(script_dir, "..", "data", "data.db")

    def fetch_latest_results(self):
        """Retrieve the latest results from the database."""
        results = []
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT domain, status, details FROM scans WHERE finished = 0")
            rows = cursor.fetchall()
            results = [{"host": row[0], "status": row[1], "details": row[2]} for row in rows]
            conn.close()
        except Exception as e:
            logging.error("Failed to fetch latest results: %s", e)
        return results

    def generate(self):
        """
        Generate an HTML report using the monitoring results.
        """
        results = self.fetch_latest_results()
        total = len(results)
        up_count = sum(1 for r in results if r["status"] == "Up")
        down_count = total - up_count
        now = datetime.now()
        display_time = now.strftime("%Y-%m-%d %H:%M:%S")

        # Updated HTML template to include "Details" column
        HTML_TEMPLATE = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Website Monitoring Report</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                h1 { color: #333; }
                table { border-collapse: collapse; width: 100%; }
                th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
                th { background-color: #f2f2f2; }
                .status-up { color: green; font-weight: bold; }
                .status-down { color: red; font-weight: bold; }
            </style>
        </head>
        <body>
            <h1>Monitoring Report</h1>
            <p><em>Report generated on: {{ display_time }}</em></p>
            {% if down == 0 %}
              <p><strong>Status:</strong> All {{ total }} hosts are UP.</p>
            {% else %}
              <p><strong>Status:</strong> {{ down }} out of {{ total }} hosts are DOWN.</p>
            {% endif %}
            <table>
                <thead>
                    <tr>
                        <th>Host</th>
                        <th>Status</th>
                        <th>Details</th>
                    </tr>
                </thead>
                <tbody>
                    {% for entry in results %}
                    <tr>
                        <td>{{ entry.host }}</td>
                        <td class="{{ 'status-up' if entry.status == 'Up' else 'status-down' }}">{{ entry.status }}</td>
                        <td>{{ entry.details }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </body>
        </html>
        """
        template = Template(HTML_TEMPLATE)
        html_content = template.render(results=results, total=total, up=up_count, down=down_count, display_time=display_time)

        try:
            with open(self.report_filename, "w", encoding="utf-8") as f:
                f.write(html_content)
            logging.info("Report generated successfully: %s", self.report_filename)
        except Exception as e:
            logging.error("Failed to write report file: %s", e)

        return self.report_filename
