import argparse
import logging
import os
import shutil
from datetime import datetime
from monitoring import Monitoring
from reports_module import Reports
from index import Index

def main():
    parser = argparse.ArgumentParser(description="Check-It Monitoring System")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--regenerate", action="store_true", help="Regenerate reports for completed scans")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO,
                        format="%(levelname)s:%(name)s:%(message)s")
    logging.info("Starting monitoring sequence...")

    # Remove /tmp/details at the start for a clean slate
    details_dir = "/tmp/details"
    if os.path.exists(details_dir):
        shutil.rmtree(details_dir)
        logging.info("Deleted %s for a clean start", details_dir)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    monitor = Monitoring(os.path.join(script_dir, "..", "data", "data.db"),
                         os.path.join(script_dir, "..", "data", "archive.db"),
                         debug=args.debug)
    monitor.run()

    report_gen = Reports(debug=args.debug)
    report_file = report_gen.generate()

    index_page = Index(os.path.join(script_dir, "..", "index.html"), debug=args.debug)
    index_page.update(report_file, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

    logging.info("Monitoring sequence completed.")

if __name__ == "__main__":
    main()
