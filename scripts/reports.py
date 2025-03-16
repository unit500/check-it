from datetime import datetime
import logging

class Reports:
    def __init__(self, debug=False):
        """
        Generates an HTML report summarizing monitoring results.
        If debug is True, logging level should be set to DEBUG for verbose output.
        """
        self.debug = debug
    
    def generate(self, results):
        """
        Generate an HTML report for the given monitoring results.
        Returns a tuple (report_filename, summary), where summary is a dict containing 
        the report timestamp and counts of total, up, and down hosts.
        """
        logging.debug("Starting report generation.")
        total = len(results)
        up_count = sum(1 for r in results if r["status"] == "Up")
        down_count = total - up_count
        current_time = datetime.now()
        timestamp_str = current_time.strftime("%Y%m%d_%H%M%S")   # for filename uniqueness
        display_time = current_time.strftime("%Y-%m-%d %H:%M:%S")  # for human-readable display
        
        # Build HTML content for the report
        html_content = []
        html_content.append("<html>")
        html_content.append("<head>")
        html_content.append("<meta charset='UTF-8'>")
        html_content.append("<title>Monitoring Report</title>")
        # Basic CSS styling for clarity
        html_content.append("<style>")
        html_content.append("body { font-family: Arial, sans-serif; }")
        html_content.append("h1 { color: #333; }")
        html_content.append("table { border-collapse: collapse; width: 100%; }")
        html_content.append("th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }")
        html_content.append("th { background-color: #f2f2f2; }")
        html_content.append(".status-up { color: green; font-weight: bold; }")
        html_content.append(".status-down { color: red; font-weight: bold; }")
        html_content.append("</style>")
        html_content.append("</head>")
        html_content.append("<body>")
        html_content.append("<h1>Monitoring Report</h1>")
        html_content.append(f"<p><em>Report generated on: {display_time}</em></p>")
        # Summary of overall status
        if down_count == 0:
            html_content.append(f"<p><strong>Status:</strong> All {total} hosts are UP.</p>")
        else:
            html_content.append(f"<p><strong>Status:</strong> {down_count} out of {total} hosts are DOWN.</p>")
        # Table of individual host results
        html_content.append("<table>")
        html_content.append("<tr><th>Host</th><th>Status</th></tr>")
        for entry in results:
            host = entry["host"]
            status = entry["status"]
            status_class = "status-up" if status == "Up" else "status-down"
            html_content.append(f"<tr><td>{host}</td><td class='{status_class}'>{status}</td></tr>")
        html_content.append("</table>")
        html_content.append("</body>")
        html_content.append("</html>")
        
        # Write the HTML report to a file
        report_filename = f"report_{timestamp_str}.html"
        try:
            with open(report_filename, "w", encoding="utf-8") as f:
                f.write("\n".join(html_content))
            logging.info("Report generated: %s (Up: %d, Down: %d)", report_filename, up_count, down_count)
        except Exception as e:
            logging.error("Failed to write report file %s: %s", report_filename, e)
        
        # Prepare a summary dict for use by the Index class
        summary = {
            "timestamp": timestamp_str,
            "display_time": display_time,
            "total": total,
            "up": up_count,
            "down": down_count
        }
        logging.debug("Report generation complete.")
        return report_filename, summary
