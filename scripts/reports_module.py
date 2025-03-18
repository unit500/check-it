import os
import random
import string
import logging
from datetime import datetime, timedelta
from jinja2 import Template

class Reports:
    def __init__(self, debug=False):
        self.debug = debug
        self.report_filename = os.path.join(os.path.dirname(__file__), "../report.html")

    def generate(self, results):
        """
        Generate an HTML report using the provided monitoring results.
        Returns the report filename.
        """
        total_checks = len(results)
        successful_checks = sum(1 for r in results if r["status"] == "Up")
        failed_checks = total_checks - successful_checks
        now = datetime.now()
        display_time = now.strftime("%Y-%m-%d %H:%M:%S")

        def generate_missing_id():
            """Generate an ID if unique_id is missing (XXX9999XXX11 format)."""
            letters = string.ascii_lowercase
            numbers = string.digits
            return (
                ''.join(random.choices(letters, k=3)) +
                ''.join(random.choices(numbers, k=4)) +
                ''.join(random.choices(letters, k=3)) +
                ''.join(random.choices(numbers, k=2))
            )

        # Ensure all records have a unique ID
        for entry in results:
            if "unique_id" not in entry or not entry["unique_id"]:
                entry["unique_id"] = generate_missing_id()

            # Calculate progress
            start_time = datetime.strptime(entry["start_time"], "%Y-%m-%d %H:%M:%S")
            duration_hours = entry["duration"]
            elapsed_time = (now - start_time).total_seconds() / 3600  # Convert to hours
            progress = min(round((elapsed_time / duration_hours) * 100, 2), 100) if duration_hours > 0 else 100

            entry["progress"] = f"{progress}%"  # Store progress as a string with %

        # HTML Report Template
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
                    <p class="text-lg mt-2">Real-time server monitoring with detailed status reports.</p>
                </div>
            </header>

            <main class="flex-1">
                <div class="container mx-auto px-4 py-10">
                    <div class="max-w-6xl mx-auto bg-white shadow-md rounded-lg p-6">
                        <div class="border-b pb-4 mb-6">
                            <h3 class="text-2xl font-semibold">Monitoring Report</h3>
                            <p class="text-gray-500 text-sm">Generated on: {{ display_time }}</p>
                        </div>

                        <p class="text-lg font-semibold mb-4">
                            Status: <span class="text-blue-500">Currently monitoring {{ total_checks }} addresses</span>
                        </p>

                        <div class="overflow-x-auto">
                            <table class="w-full border border-gray-300 text-sm text-left">
                                <thead class="bg-blue-50 text-blue-900">
                                    <tr>
                                        <th class="border border-gray-300 px-4 py-2">ID</th>
                                        <th class="border border-gray-300 px-4 py-2">Host</th>
                                        <th class="border border-gray-300 px-4 py-2">Status</th>
                                        <th class="border border-gray-300 px-4 py-2">Progress</th>
                                        <th class="border border-gray-300 px-4 py-2">Details</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {% for entry in results %}
                                    <tr class="border border-gray-300">
                                        <td class="px-4 py-2 font-semibold">{{ entry.unique_id }}</td>
                                        <td class="px-4 py-2">{{ entry.host }}</td>
                                        <td class="px-4 py-2">
                                            {% if entry.status == "Up" %}
                                                <span class="inline-flex px-2 py-1 rounded-full bg-green-100 text-green-800 font-semibold">Up</span>
                                            {% else %}
                                                <span class="inline-flex px-2 py-1 rounded-full bg-red-100 text-red-800 font-semibold">Down</span>
                                            {% endif %}
                                        </td>
                                        <td class="px-4 py-2 font-semibold text-blue-700">{{ entry.progress }}</td>
                                        <td class="px-4 py-2 text-gray-600">{{ entry.details }}</td>
                                    </tr>
                                    {% endfor %}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </main>

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
        html_content = template.render(
            results=results,
            total_checks=total_checks,
            successful_checks=successful_checks,
            failed_checks=failed_checks,
            display_time=display_time
        )

        try:
            with open(self.report_filename, "w", encoding="utf-8") as f:
                f.write(html_content)
            logging.info("Report generated successfully: %s", self.report_filename)
        except Exception as e:
            logging.error("Failed to write report file %s: %s", self.report_filename, e)

        return self.report_filename
