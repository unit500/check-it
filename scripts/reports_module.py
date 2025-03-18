from datetime import datetime
from jinja2 import Template
import logging
import random
import string

class Reports:
    def __init__(self, debug=False):
        self.debug = debug

    def generate(self, results):
        """
        Generate an HTML report using the provided monitoring results.
        Returns a tuple (report_filename, summary).
        """
        total_checks = len(results)
        successful_checks = sum(1 for r in results if r["status"] == "Up")
        failed_checks = total_checks - successful_checks
        now = datetime.now()
        display_time = now.strftime("%Y-%m-%d %H:%M:%S")
        
        # Calculate progress percentage
        progress = round((successful_checks / total_checks) * 100, 2) if total_checks > 0 else 0
        
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

                        <div class="mb-6">
                            <table class="w-full border border-gray-300 text-sm text-left">
                                <thead class="bg-blue-50 text-blue-900">
                                    <tr>
                                        <th class="border border-gray-300 px-4 py-2">Progress</th>
                                        <td class="border border-gray-300 px-4 py-2 font-semibold text-green-700">{{ progress }}%</td>
                                    </tr>
                                    <tr>
                                        <th class="border border-gray-300 px-4 py-2">Total Checks</th>
                                        <td class="border border-gray-300 px-4 py-2">{{ total_checks }}</td>
                                    </tr>
                                    <tr>
                                        <th class="border border-gray-300 px-4 py-2">Successful Checks</th>
                                        <td class="border border-gray-300 px-4 py-2 text-green-600">{{ successful_checks }}</td>
                                    </tr>
                                    <tr>
                                        <th class="border border-gray-300 px-4 py-2">Failed Checks</th>
                                        <td class="border border-gray-300 px-4 py-2 text-red-600">{{ failed_checks }}</td>
                                    </tr>
                                    <tr>
                                        <th class="border border-gray-300 px-4 py-2">Last Check Time</th>
                                        <td class="border border-gray-300 px-4 py-2 text-gray-500">{{ display_time }}</td>
                                    </tr>
                                </thead>
                            </table>
                        </div>

                        <div class="overflow-x-auto">
                            <table class="w-full border border-gray-300 text-sm text-left">
                                <thead class="bg-blue-50 text-blue-900">
                                    <tr>
                                        <th class="border border-gray-300 px-4 py-2">ID</th>
                                        <th class="border border-gray-300 px-4 py-2">Host</th>
                                        <th class="border border-gray-300 px-4 py-2">Status</th>
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
            progress=progress,
            display_time=display_time
        )

        report_filename = "../report.html"
        try:
            with open(report_filename, "w", encoding="utf-8") as f:
                f.write(html_content)
            logging.info("Report generated successfully as %s", report_filename)
        except Exception as e:
            logging.error("Failed to write report file %s: %s", report_filename, e)

        return report_filename
