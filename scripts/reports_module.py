import sqlite3
import logging
import os
from datetime import datetime
from jinja2 import Template

class Reports:
    def __init__(self, db_path=None, archive_path=None, output_path=None, debug=False):
        """Initialize the report generation class with database paths."""
        self.debug = debug
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.db_path = db_path if db_path else os.path.join(script_dir, "..", "data", "data.db")
        self.archive_path = archive_path if archive_path else os.path.join(script_dir, "..", "data", "archive.db")
        self.output_path = output_path if output_path else os.path.join(script_dir, "..", "report.html")

    def fetch_latest_results(self):
        """Fetch latest active scan results from data.db."""
        results = []
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT start_time, status, domain, total_scans, successful_scans, failed_scans, last_scan_time, details, duration 
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
        """Fetch latest 10 completed scans from archive.db."""
        results = []
        try:
            conn = sqlite3.connect(self.archive_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT start_time, status, domain, total_scans, successful_scans, failed_scans, last_scan_time, details, duration 
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
        """Calculate progress as a percentage based on start time and duration."""
        try:
            start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
            now = datetime.now()
            elapsed_time = (now - start_dt).total_seconds() / 3600  # Convert to hours
            progress = min(round((elapsed_time / duration) * 100, 2), 100) if duration > 0 else 100
            return f"{progress}%"
        except Exception:
            return "N/A"

    def generate(self):
        """Generate an HTML report for active scans and latest completed scans."""
        active_scans = self.fetch_latest_results()
        completed_scans = self.fetch_latest_completed_scans()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Add progress calculation to each scan entry
        active_scans_with_progress = [
            list(row) + [self.calculate_progress(row[0], row[8])] for row in active_scans
        ]
        completed_scans_with_progress = [
            list(row) + [self.calculate_progress(row[0], row[8])] for row in completed_scans
        ]

        # HTML Template with Tailwind CSS
        HTML_TEMPLATE = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Reports | Check-It Uptime Monitoring</title>
            <script src="https://cdn.tailwindcss.com"></script>
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
                                    {{ active_scans_with_progress | selectattr('1', 'equalto', 'Down') | list | length }} out of {{ active_scans_with_progress | length }} hosts are DOWN
                                </span>
                            {% else %}
                                <span class="text-green-500">No active scans</span>
                            {% endif %}
                        </p>

                        <div class="overflow-x-auto">
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
                                        <td class="px-4 py-2 text-gray-500">{{ row[0] }}</td>
                                        <td class="px-4 py-2 {% if row[1] == 'Up' %} text-green-600 {% else %} text-red-600 {% endif %}">{{ row[1] }}</td>
                                        <td class="px-4 py-2 font-medium">{{ row[2] }}</td>
                                        <td class="px-4 py-2 text-blue-600 font-semibold">{{ row[9] }}</td>
                                        <td class="px-4 py-2">{{ row[3] }}</td>
                                        <td class="px-4 py-2">{{ row[4] }}</td>
                                        <td class="px-4 py-2">{{ row[5] }}</td>
                                        <td class="px-4 py-2 text-gray-500">{{ row[6] }}</td>
                                        <td class="px-4 py-2 text-gray-600">{{ row[7] }}</td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>

                        <hr class="my-10 border-gray-300">
                        <h3 class="text-xl font-semibold mb-4">Latest 10 Completed Checks</h3>

                        <div class="overflow-x-auto">
                            <table class="min-w-full border border-gray-300 text-sm text-left">
                                <tbody>
                                    {% for row in completed_scans_with_progress %}
                                    <tr class="border border-gray-300 {% if loop.index is even %} bg-gray-50 {% endif %}">
                                        <td class="px-4 py-2 text-gray-500">{{ row[0] }}</td>
                                        <td class="px-4 py-2">{{ row[1] }}</td>
                                        <td class="px-4 py-2 font-medium">{{ row[2] }}</td>
                                        <td class="px-4 py-2 text-blue-600 font-semibold">{{ row[9] }}</td>
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
        html_content = template.render(now=now, active_scans_with_progress=active_scans_with_progress, completed_scans_with_progress=completed_scans_with_progress)

        with open(self.output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
