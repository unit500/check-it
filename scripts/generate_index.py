import os
from jinja2 import Environment, FileSystemLoader
import datetime

template_dir = os.path.join(os.path.dirname(__file__), "../templates")
env = Environment(loader=FileSystemLoader(template_dir))
template = env.get_template("index.html")
current_year = datetime.datetime.now().year
output = template.render(current_year=current_year)
with open("../index.html", "w") as f:
    f.write(output)
print("Index page generated successfully.")
