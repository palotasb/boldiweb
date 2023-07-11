import argparse
import collections
import itertools
import json
import re
import shutil
from dataclasses import InitVar, dataclass, field
from pathlib import Path
from typing import Any, Generator, Optional

import jinja2
from exiftool import ExifToolHelper
from unidecode import unidecode

from boldibuild import Build, Stamp, Target

# source folder -> image list
# image list -> exif db
# exif db -> exif data
# image list + exif db -> output images
# output images + templates -> output html


IMAGE_EXTENSIONS = (".JPG", ".JPEG", ".PNG", ".GIF")
HERE = Path(__file__).parent.resolve()
NON_URL_SAFE_RE = re.compile(r"[^\w\d\.\-_/]+", re.ASCII)
RELEVANT_EXIF_TAGS = ("EXIF:all", "IPTC:all")


exiftool = ExifToolHelper().__enter__()


def get_exif_tags(image_path: Path) -> dict[str, Any]:
    raw_tags = exiftool.get_tags(str(image_path), RELEVANT_EXIF_TAGS)[0]
    tags = collections.defaultdict(dict)
    for key, value in raw_tags.items():
        assert isinstance(key, str)
        if ":" not in key:
            tags[key] = value
        else:
            category, tag = key.split(":", 1)
            tags[category][tag] = value
    tags["SourceFile"] = image_path.name
    return dict(tags)


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
    exif_path: Path = field(init=False)

    def __post_init__(self):
        super().__setattr__("orig_name", self.orig_path.name)
        super().__setattr__("exif_path", self.path.with_suffix(".exif.json"))


@dataclass(eq=True, order=True, frozen=True)
class TargetFolder:
    source_folder: SourceFolder
    path: Path
    orig_path: Path
    orig_name: str = field(init=False)
    subfolders: dict[str, "TargetFolder"] = field(init=False, default_factory=dict)
    images: dict[str, TargetImage] = field(init=False, default_factory=dict)

    def __post_init__(self):
        super().__setattr__("orig_name", self.orig_path.name)
        for source_subfolder in self.source_folder.subfolders:
            name = Path(source_subfolder.path.name)
            target_folder = TargetFolder(
                source_subfolder,
                self.path / ascii_path(name),
                self.orig_path / name,
            )
            self.subfolders[target_folder.path.name] = target_folder
        for source_image in self.source_folder.images:
            name = Path(source_image.path.name)
            target_image = TargetImage(
                source_image, self.path / ascii_path(name), self.orig_path / name
            )
            self.images[target_image.path.name] = target_image

    def path_to_folder(self, path: Path) -> Optional["TargetFolder"]:
        if path.is_absolute():
            return None
        elif path == Path("."):
            return self
        else:
            subfolder = self.subfolders.get(path.parts[0])
            if subfolder is not None:
                return subfolder.path_to_folder(Path(*path.parts[1:]))
            else:
                return None

    def path_to_image(self, path: Path) -> Optional[TargetImage]:
        folder = self.path_to_folder(Path(*path.parts[:-1]))
        if folder is not None:
            return folder.images.get(path.name)
        else:
            return None

    def iter_images(self) -> Generator[TargetImage, None, None]:
        for image in itertools.chain(
            self.images.values(),
            *[subfolder.iter_images() for subfolder in self.subfolders.values()],
        ):
            yield image


@dataclass
class Album(Build):
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
        self.load_build_db()

    def stamp_target_image(self, image: TargetImage):
        return "; ".join(
            [
                self.stamp_file_stat(self.target_abs_path / image.path),
                self.stamp_file_stat(self.target_abs_path / image.exif_path),
            ]
        )

    def build_target_image(self, image: TargetImage):
        (self.target_abs_path / image.path).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(image.source_image.path, self.target_abs_path / image.path)

        # TODO: create thumbnail images

        with open(self.target_abs_path / image.exif_path, "w") as exif_fp:
            json.dump(get_exif_tags(image.source_image.path), exif_fp, indent=2)

        self.register_dependency(str(image.path), str(image.source_image.path))

    def stamp(self, target: Target) -> Stamp:
        if image := self.target.path_to_image(Path(target)):
            return self.stamp_target_image(image)
        else:
            path = Path(target)
            if path.is_absolute() and path.is_file():
                return self.stamp_file_stat(target)
            else:
                raise NotImplementedError(f"stamp not implemented for {target=!r}")

    def build_implementation(self, target: Target):
        if image := self.target.path_to_image(Path(target)):
            self.build_target_image(image)
        else:
            NotImplemented  # but do nothing

    def render(self):
        # DONE Create output folder structure
        for image in self.target.iter_images():
            self.build(str(image.path))

        # TODO Call .build() on output images
        self.render_folder(self.target)
        self.save_build_db()

    def render_folder(self, folder: TargetFolder):
        target_abs_path = self.target_abs_path / folder.path / "index.html"
        target_abs_path.parent.mkdir(parents=True, exist_ok=True)

        index_template = self.env.get_template("index.html")
        stream = index_template.stream({"folder": folder})
        with open(target_abs_path, "w") as fp:
            stream.dump(fp)

        for subfolder in folder.subfolders.values():
            self.render_folder(subfolder)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_path", type=Path)
    parser.add_argument("target_path", type=Path)
    args = parser.parse_args()
    source_path: Path = args.source_path
    target_path: Path = args.target_path
    album = Album(target_path / "build.db.json", target_path, source_path)
    album.render()


if __name__ == "__main__":
    main()

exiftool.__exit__(None, None, None)
