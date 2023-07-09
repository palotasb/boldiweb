import argparse
import re
from dataclasses import InitVar, dataclass, field
from pathlib import Path

import jinja2
from unidecode import unidecode

IMAGE_EXTENSIONS = (".JPG", ".JPEG", ".PNG", ".GIF")
HERE = Path(__file__).parent.resolve()
NON_URL_SAFE_RE = re.compile(r"[^\w\d\.\-_/]+", re.ASCII)


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


def full_relative_to(target: Path, relative_to: Path) -> Path:
    target = Path(target)  # actually accept str objects too
    relative_to = Path(relative_to)
    for i, relative_to_parents in enumerate([relative_to] + list(relative_to.parents)):
        if target.is_relative_to(relative_to_parents):
            return Path(*([Path("..")] * i)) / target.relative_to(relative_to_parents)


def ascii_path(path: Path) -> Path:
    path_str = unidecode(str(path))
    path_str = NON_URL_SAFE_RE.sub("_", path_str)
    return Path(path_str)


@dataclass(eq=True, order=True, frozen=True)
class TargetImage:
    source_image: SourceImage
    path: Path
    orig_path: Path
    orig_name: str = field(init=False)

    def __post_init__(self):
        super().__setattr__("orig_name", self.orig_path.name)


@dataclass(eq=True, order=True, frozen=True)
class TargetFolder:
    source_folder: SourceFolder
    path: Path
    orig_path: Path
    orig_name: str = field(init=False)
    subfolders: list["TargetFolder"] = field(init=False, default_factory=list)
    images: list[TargetImage] = field(init=False, default_factory=list)

    def __post_init__(self):
        super().__setattr__("orig_name", self.orig_path.name)
        for source_subfolder in self.source_folder.subfolders:
            name = Path(source_subfolder.path.name)
            self.subfolders.append(
                TargetFolder(
                    source_subfolder,
                    self.path / ascii_path(name),
                    self.orig_path / name,
                )
            )
        for source_image in self.source_folder.images:
            name = Path(source_image.path.name)
            self.images.append(
                TargetImage(
                    source_image, self.path / ascii_path(name), self.orig_path / name
                )
            )


@dataclass
class Album:
    target_path: InitVar[Path]
    source_path: InitVar[Path]
    source: SourceFolder = field(init=False)
    target: TargetFolder = field(init=False)
    target_abs_path: Path = field(init=False)
    env: jinja2.Environment = field(init=False)

    def __post_init__(self, target_path: Path, source_path: Path):
        self.source = SourceFolder(source_path)
        self.target = TargetFolder(self.source, Path("."), Path("."))
        self.target_abs_path = target_path
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
            "root": Path("."),
        }
        self.env.filters["relative_to"] = full_relative_to
        self.env.filters["ascii_path"] = ascii_path

    def render(self):
        self.render_folder(self.target)

    def render_folder(self, folder: TargetFolder):
        target_abs_path = self.target_abs_path / folder.path / "index.html"
        target_abs_path.parent.mkdir(parents=True, exist_ok=True)

        index_template = self.env.get_template("index.html")
        stream = index_template.stream({"folder": folder})
        with open(target_abs_path, "w") as fp:
            stream.dump(fp)

        for subfolder in folder.subfolders:
            self.render_folder(subfolder)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_path", type=Path)
    parser.add_argument("target_path", type=Path)
    args = parser.parse_args()
    source_path: Path = args.source_path
    target_path: Path = args.target_path
    album = Album(target_path, source_path)
    album.render()


if __name__ == "__main__":
    main()
