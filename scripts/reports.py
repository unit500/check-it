from datetime import datetime
from jinja2 import Template
import logging
import os

class Reports:
    def __init__(self, debug=False):
        self.debug = debug
        # Get the absolute path of the directory where this script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Ensure the report is generated inside the correct directory
        self.report_filename = os.path.join(script_dir, "..", "report.html")

    def generate(self, results):
        """
        Generate an HTML report using the provided monitoring results.
        The report is always saved as 'report.html' (so users can reliably access it).
        Returns a tuple (report_filename, summary) for use by the Index class.
        """
        total = len(results)
        up_count = sum(1 for r in results if r["status"] == "Up")
        down_count = total - up_count
        now = datetime.now()
        display_time = now.strftime("%Y-%m-%d %H:%M:%S")

        # Build the HTML content using a Jinja2 template.
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
                    </tr>
                </thead>
                <tbody>
                    {% for entry in results %}
                    <tr>
                        <td>{{ entry.host }}</td>
                        <td class="{{ 'status-up' if entry.status == 'Up' else 'status-down' }}">{{ entry.status }}</td>
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
            logging.info("Report generated successfully as %s (Up: %d, Down: %d)", self.report_filename, up_count, down_count)
        except Exception as e:
            logging.error("Failed to write report file %s: %s", self.report_filename, e)

        summary = {
            "display_time": display_time,
            "total": total,
            "up": up_count,
            "down": down_count
        }
        return self.report_filename, summary
