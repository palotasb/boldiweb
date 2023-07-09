import argparse
from dataclasses import dataclass, field
from pathlib import Path

import jinja2

IMAGE_EXTENSIONS = (".JPG", ".JPEG", ".PNG", ".GIF")
HERE = Path(__file__).parent.resolve()


@dataclass(eq=True, order=True, frozen=True)
class SourceImage:
    path: Path


@dataclass(eq=True, order=True, frozen=True)
class SourceFolder:
    path: Path
    subfolders: list["SourceFolder"] = field(default_factory=list, init=False)
    images: list[SourceImage] = field(default_factory=list, init=False)
    ignored_items: list[Path] = field(default_factory=list, init=False)

    def __post_init__(self):
        for item in sorted(self.path.iterdir()):
            if (
                item.is_file()
                and item.suffix.upper() in IMAGE_EXTENSIONS
                and not item.name.startswith(".")
            ):
                self.images.append(SourceImage(item))
            elif item.is_dir() and not item.name.startswith("."):
                self.subfolders.append(SourceFolder(item))
            else:
                self.ignored_items.append(item)

    def __hash__(self) -> int:
        return hash(self.path)


def relative_path(target: Path, relative_to: Path) -> Path:
    for i, relative_to_parents in enumerate([relative_to] + list(relative_to.parents)):
        if target.is_relative_to(relative_to_parents):
            return Path(*([Path("..")] * i)) / target.relative_to(relative_to_parents)


@dataclass
class Album:
    root_folder: SourceFolder
    target: Path
    env: jinja2.Environment = field(init=False)
    index_template: jinja2.Template = field(init=False)

    def __post_init__(self):
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(HERE / "templates"),
            autoescape=True,
            block_start_string="<j2:block>",
            block_end_string="</j2:block>",
            variable_start_string="<j2:var>",
            variable_end_string="</j2:var>",
            comment_start_string="<j2:comment>",
            comment_end_string="</j2:comment>",
            keep_trailing_newline=True,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self.env.globals = {
            "album": self,
            "target": self.target,
        }
        self.env.filters["relative_to"] = relative_path
        self.index_template = self.env.get_template("index.html")

    def render(self):
        self.render_folder(self.root_folder)

    def render_folder(self, folder: SourceFolder):
        stream = self.index_template.stream(
            {
                "folder": folder,
            }
        )
        target_path = (
            self.target
            / relative_path(folder.path, self.root_folder.path)
            / "index.html"
        )
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w") as fp:
            stream.dump(fp)

        for subfolder in folder.subfolders:
            self.render_folder(subfolder)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root_path", type=Path)
    parser.add_argument("output_path", type=Path)
    args = parser.parse_args()
    root_path: Path = args.root_path
    output_path: Path = args.output_path
    album = Album(SourceFolder(root_path), output_path)
    album.render()


if __name__ == "__main__":
    main()
