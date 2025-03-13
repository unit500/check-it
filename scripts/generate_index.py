import os
from jinja2 import Environment, FileSystemLoader
import datetime

# Set the directory where your templates are stored
template_dir = os.path.join(os.path.dirname(__file__), "../templates")
env = Environment(loader=FileSystemLoader(template_dir))

# Load the index template
template = env.get_template("index.html")

# Prepare context variables for the template
current_year = datetime.datetime.now().year

# Render the template with context
output = template.render(current_year=current_year)

# Write the rendered output to index.html in the repo root
with open("../index.html", "w") as f:
    f.write(output)

print("Index page generated successfully.")
