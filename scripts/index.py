import logging

class Index:
    def __init__(self, debug=False):
        """
        Updates the index page for displaying results.
        If debug is True, logging level should be set to DEBUG for verbose output.
        """
        self.debug = debug
        self.index_file = "index.html"
    
    def update(self, report_filename, summary):
        """
        Update (or create) the index page with an entry for the latest report.
        Each entry includes the report date/time, total hosts, number up, and number down.
        """
        logging.debug("Updating index page.")
        # Extract info for the new index entry
        display_time = summary.get("display_time", report_filename)
        total = summary.get("total", "")
        up = summary.get("up", "")
        down = summary.get("down", "")
        # Construct a new table row linking to the report
        if isinstance(down, int) and down > 0:
            # Highlight the "Down" count in red if any hosts are down
            new_row = (f"<tr><td><a href=\"{report_filename}\">{display_time}</a></td>"
                       f"<td>{total}</td><td>{up}</td>"
                       f"<td style='color: red; font-weight: bold;'>{down}</td></tr>\n")
        else:
            new_row = (f"<tr><td><a href=\"{report_filename}\">{display_time}</a></td>"
                       f"<td>{total}</td><td>{up}</td><td>{down}</td></tr>\n")
        
        try:
            # Read existing index file if it exists
            try:
                with open(self.index_file, "r", encoding="utf-8") as f:
                    content = f.read()
            except FileNotFoundError:
                content = ""
            
            if content:
                logging.debug("Index page exists. Adding new entry to it.")
                # Insert the new row right after the header row in the table
                insert_pos = content.find("</tr>")  # end of the header row
                if insert_pos != -1:
                    insert_pos += len("</tr>")
                    content = content[:insert_pos] + "\n" + new_row + content[insert_pos:]
                else:
                    # If the table structure isn't found, we'll recreate it from scratch
                    content = ""
            
            if not content:
                logging.debug("Creating a new index page with table header.")
                # Build a new index page (with table headers) if none exists
                content_lines = [
                    "<html>",
                    "<head>",
                    "<meta charset='UTF-8'>",
                    "<title>Monitoring Reports Index</title>",
                    "<style>",
                    "body { font-family: Arial, sans-serif; }",
                    "h1 { color: #333; }",
                    "table { border-collapse: collapse; width: 100%; }",
                    "th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }",
                    "th { background-color: #f2f2f2; }",
                    "</style>",
                    "</head>",
                    "<body>",
                    "<h1>Monitoring Reports Index</h1>",
                    "<table>",
                    "<tr><th>Date/Time</th><th>Total</th><th>Up</th><th>Down</th></tr>",
                    new_row.strip(),  # add the first entry (strip to remove trailing newline)
                    "</table>",
                    "</body>",
                    "</html>"
                ]
                content = "\n".join(content_lines)
            
            # Write the updated content back to the index file
            with open(self.index_file, "w", encoding="utf-8") as f:
                f.write(content)
            logging.info("Index page updated: %s", self.index_file)
        except Exception as e:
            logging.error("Failed to update index page: %s", e)
