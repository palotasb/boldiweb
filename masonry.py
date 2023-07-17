from pathlib import Path

import jinja2

HERE = Path(__file__).parent.resolve()

env = jinja2.Environment(loader=jinja2.FileSystemLoader(HERE / "templates"))
env.get_template("masonry.html.j2").stream().dump("out/masonry.html")
