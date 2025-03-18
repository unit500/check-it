from datetime import datetime
from jinja2 import Template
import logging
import os
import sqlite3

class Reports:
    def __init__(self, debug=False):
        """Initialize report generation, set file paths."""
        self.debug = debug
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.report_filename = os.path.join(script_dir, "..", "report.html")
        self.db_path = os.path.join(script_dir, "..", "data", "data.db")

    def fetch_latest_results(self):
        """Retrieve the latest results from the database, including scan statistics."""
        results = []
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT 
                    domain, status, details, start_time, last_scan_time,
                    total_scans, successful_scans, failed_scans
                FROM scans WHERE finished = 0
            """)
            rows = cursor.fetchall()
            results = [
                {
                    "host": row[0],
                    "status": row[1],
                    "details": row[2] if row[2] else "No details available",
                    "start_time": row[3] if row[3] else "N/A",
                    "last_scan_time": row[4] if row[4] else "N/A",
                    "total_scans": row[5] if row[5] else 0,
                    "successful_scans": row[6] if row[6] else 0,
                    "failed_scans": row[7] if row[7] else 0,
                }
                for row in rows
            ]
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

        # Updated HTML template with new columns for scan statistics
        HTML_TEMPLATE = """
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Reports | Check-It Uptime Monitoring</title>
            <!-- Tailwind CSS via CDN -->
            <script src="https://cdn.tailwindcss.com"></script>
        </head>
        <body class="min-h-screen flex flex-col bg-gradient-to-b from-white to-gray-50">

            <!-- Header -->
            <header class="w-full bg-gradient-to-r from-blue-900 to-blue-700 text-white shadow-lg">
                <div class="container mx-auto py-6 px-4 text-center">
                    <h1 class="text-3xl font-bold tracking-tight">Check-It Uptime Monitoring</h1>
                    <p class="text-monitor-100 text-lg mt-2">
                        Real-time server monitoring with detailed status reports.
                    </p>
                </div>
            </header>

            <!-- Main Content -->
            <main class="flex-1">
                <div class="container mx-auto px-4 py-10">
                    <div class="max-w-6xl mx-auto bg-white shadow-md rounded-lg p-6">
                        <div class="border-b pb-4 mb-6">
                            <h3 class="text-2xl font-semibold">Monitoring Report</h3>
                            <p class="text-gray-500 text-sm">Generated on: {{ display_time }}</p>
                        </div>

                        <p class="text-lg font-semibold mb-4">
                            Status: 
                            {% if down_count == 0 %}
                                <span class="text-green-500">All {{ total }} hosts are UP</span>
                            {% else %}
                                <span class="text-red-500">{{ down_count }} out of {{ total }} hosts are DOWN</span>
                            {% endif %}
                        </p>

                        <!-- Table -->
                        <div class="overflow-x-auto">
                            <table class="min-w-full border border-gray-300 text-sm text-left">
                                <thead class="bg-blue-50 text-blue-900">
                                    <tr>
                                        <th class="border border-gray-300 px-4 py-2">Start Time</th>
                                        <th class="border border-gray-300 px-4 py-2">Status</th>
                                        <th class="border border-gray-300 px-4 py-2">Host</th>
                                        <th class="border border-gray-300 px-4 py-2">Total Scans</th>
                                        <th class="border border-gray-300 px-4 py-2">Successful Scans</th>
                                        <th class="border border-gray-300 px-4 py-2">Failed Scans</th>
                                        <th class="border border-gray-300 px-4 py-2">Last Scan Time</th>
                                        <th class="border border-gray-300 px-4 py-2">Details</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for entry in results %}
                                    <tr class="border border-gray-300 {% if loop.index is even %} bg-gray-50 {% endif %}">
                                        <td class="px-4 py-2 text-gray-500">{{ entry.start_time }}</td>
                                        <td class="px-4 py-2">
                                            {% if entry.status == "Up" %}
                                                <span class="inline-flex px-2 py-1 rounded-full bg-green-100 text-green-800 font-semibold">Up</span>
                                            {% else %}
                                                <span class="inline-flex px-2 py-1 rounded-full bg-red-100 text-red-800 font-semibold">Down</span>
                                            {% endif %}
                                        </td>
                                        <td class="px-4 py-2 font-medium">{{ entry.host }}</td>
                                        <td class="px-4 py-2 text-gray-600">{{ entry.total_scans }}</td>
                                        <td class="px-4 py-2 text-green-600">{{ entry.successful_scans }}</td>
                                        <td class="px-4 py-2 text-red-600">{{ entry.failed_scans }}</td>
                                        <td class="px-4 py-2 text-gray-500">{{ entry.last_scan_time }}</td>
                                        <td class="px-4 py-2 text-gray-600">{{ entry.details }}</td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </main>

            <!-- Footer -->
            <footer class="bg-gray-900 text-gray-400 py-6 text-center">
                <p class="text-sm">Check-It &copy; <span id="currentYear"></span> - Open Source Uptime Monitoring</p>
            </footer>

            <script>
                document.getElementById('currentYear').textContent = new Date().getFullYear();
            </script>
        </body>
        </html>
        """
        template = Template(HTML_TEMPLATE)
        html_content = template.render(results=results, total=total, up_count=up_count, down_count=down_count, display_time=display_time)

        try:
            with open(self.report_filename, "w", encoding="utf-8") as f:
                f.write(html_content)
            logging.info("Report generated successfully: %s", self.report_filename)
        except Exception as e:
            logging.error("Failed to write report file: %s", e)

        return self.report_filename
