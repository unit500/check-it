import argparse
import logging
from monitoring import Monitoring
from reports_module import Reports
from index import Index

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Monitor remote computers and generate HTML reports.")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    parser.add_argument("--regenerate", action="store_true", help="Regenerate files for archived scans from last 7 days.")
    args = parser.parse_args()
    
    # ...
    logging.basicConfig(level=logging.DEBUG if args.debug else logging.INFO)
    
    logging.info("Starting monitoring sequence...")
    
    monitor = Monitoring(debug=args.debug)
    results = monitor.run()

    report_gen = Reports(debug=args.debug)
    # Pass the regenerate flag to the Reports instance
    report_gen.regenerate_mode = args.regenerate
    report_file = report_gen.generate()

    # ...
    index_page = Index(debug=args.debug)
    index_page.update(report_file, {"display_time": "N/A"})
    
    logging.info("Monitoring sequence completed.")
