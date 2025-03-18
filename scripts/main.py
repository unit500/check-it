import argparse
import logging
from monitoring import Monitoring
from reports_module import Reports  # Ensure the correct module name
from index import Index

if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Monitor remote computers and generate HTML reports.")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging for detailed output.")
    args = parser.parse_args()
    
    # Configure logging level based on --debug flag
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")
    
    logging.info("Starting monitoring sequence...")
    
    # Run monitoring checks
    monitor = Monitoring(debug=args.debug)
    results = monitor.run()  # Fetch results
    
    # Generate HTML report from results
    report_gen = Reports(debug=args.debug)
    report_file = report_gen.generate(results)  # FIXED: Passing 'results' correctly

    # Update index page with the new report info
    index_page = Index(debug=args.debug)
    index_page.update(report_file, {"display_time": "N/A"})  # Adjusted for now

    logging.info("Monitoring sequence completed.")
