import argparse
import collections
import functools
import itertools
import json
import logging
import re
import shutil
from dataclasses import InitVar, dataclass, field
from pathlib import Path
from typing import Any, Generator, Optional

import jinja2
from exiftool import ExifToolHelper
from unidecode import unidecode

from boldibuild import Build, FileHandler, RegisterDependencyCallback, Stamp, Target

# source folder -> image list
# image list -> exif db
# exif db -> exif data
# image list + exif db -> output images
# output images + templates -> output html


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


IMAGE_EXTENSIONS = (".JPG", ".JPEG", ".PNG", ".GIF")
HERE = Path(__file__).parent.resolve()
NON_URL_SAFE_RE = re.compile(r"[^\w\d\.\-_/]+", re.ASCII)
RELEVANT_EXIF_TAGS = ("EXIF:all", "IPTC:all")


exiftool = ExifToolHelper().__enter__()


def get_exif_tags(image_path: Path) -> dict[str, Any]:
    raw_exif_tags = exiftool.get_tags(str(image_path), RELEVANT_EXIF_TAGS)[0]
    assert isinstance(raw_exif_tags, dict)
    exif_tags = collections.defaultdict(dict)
    for key, value in raw_exif_tags.items():
        assert isinstance(key, str)
        if ":" not in key:
            exif_tags[key] = value
        else:
            category, tag = key.split(":", 1)
            exif_tags[category][tag] = value
    exif_tags["SourceFile"] = image_path.name
    for category, category_tags in exif_tags.items():
        if isinstance(category_tags, dict):
            exif_tags[category] = dict(sorted(category_tags.items()))
    return dict(exif_tags)


def relative_to(path: Path, other: Path) -> Path:
    path, other = Path(path), Path(other)  # actually accept str objects too
    for i, relative_to_parents in enumerate([other] + list(other.parents)):
        if path.is_relative_to(relative_to_parents):
            return Path(*([Path("..")] * i)) / path.relative_to(relative_to_parents)


def to_safe_ascii(s: str) -> str:
    return NON_URL_SAFE_RE.sub("_", unidecode(s))


@dataclass
class SourceImage:
    path: Path


@dataclass
class SourceFolder:
    path: Path
    subfolders: dict[str, "SourceFolder"] = field(init=False, default_factory=dict)
    images: dict[str, SourceImage] = field(init=False, default_factory=dict)

    def __post_init__(self):
        for abs_sub_path in sorted(self.path.iterdir()):
            name = abs_sub_path.name
            if name.startswith("."):
                pass
            elif abs_sub_path.is_file() and abs_sub_path.suffix.upper() in IMAGE_EXTENSIONS:
                self.images[name] = SourceImage(abs_sub_path)
            elif abs_sub_path.is_dir():
                self.subfolders[name] = SourceFolder(abs_sub_path)


@dataclass
class TargetImage:
    source: SourceImage
    parent: "TargetFolder"
    path: Path

    @property
    def exif_json_path(self) -> Path:
        return self.path.with_suffix(".exif.json")

    @functools.cached_property
    def exif_data(self) -> dict[str, Any]:
        return json.loads(self.exif_json_path.read_text())


@dataclass
class TargetFolder:
    source: SourceFolder
    parent: Optional["TargetFolder"]
    path: Path
    subfolders: dict[str, "TargetFolder"] = field(init=False, default_factory=dict)
    images: dict[str, TargetImage] = field(init=False, default_factory=dict)

    def __post_init__(self):
        for source_subfolder in self.source.subfolders.values():
            safe_ascii_name = to_safe_ascii(source_subfolder.path.name)
            subfolder = TargetFolder(
                source_subfolder,
                self,
                self.path / safe_ascii_name,
            )
            self.subfolders[safe_ascii_name] = subfolder
        for source_image in self.source.images.values():
            safe_ascii_name = to_safe_ascii(source_image.path.name)
            image = TargetImage(source_image, self, self.path / safe_ascii_name)
            self.images[safe_ascii_name] = image

    def path_to_folder(self, path: Path) -> Optional["TargetFolder"]:
        if path.is_absolute() and path.is_relative_to(self.path):
            path = path.relative_to(self.path)
        elif path.is_absolute():
            return None

        if path == Path("."):
            return self
        else:
            subfolder = self.subfolders.get(path.parts[0])
            return subfolder.path_to_folder(Path(*path.parts[1:])) if subfolder else None

    def path_to_image(self, path: Path) -> Optional[TargetImage]:
        folder = self.path_to_folder(Path(*path.parts[:-1]))
        return folder.images.get(path.name) if folder else None

    def iter_all_images(self) -> Generator[TargetImage, None, None]:
        for image in itertools.chain(
            self.images.values(),
            *[subfolder.iter_all_images() for subfolder in self.subfolders.values()],
        ):
            yield image


@dataclass
class TargetFolderHandler(FileHandler):
    album: "Album"

    def maybe_target_folder(self, target: Stamp) -> Optional[TargetFolder]:
        return self.album.target_root.path_to_folder(Path(target))

    def target_folder(self, target: Stamp) -> TargetFolder:
        maybe_target_folder = self.maybe_target_folder(target)
        assert maybe_target_folder
        return maybe_target_folder

    def can_handle(self, target: Target) -> bool:
        return self.maybe_target_folder(target) is not None

    def build_impl(self, target: Target, register_dependency: RegisterDependencyCallback):
        target_folder = self.target_folder(target)

        target_folder.path.mkdir(parents=True, exist_ok=True)
        register_dependency(str(target_folder.source.path))

        for subfolder in target_folder.subfolders.values():
            self.album.build(str(subfolder.path))
            register_dependency(str(subfolder.path))

        for image in target_folder.images.values():
            self.album.build(str(image.path))
            register_dependency(str(image.path))

        index_html = target_folder.path / "index.html"

        index_template = self.album.env.get_template("index.html")
        stream = index_template.stream({"folder": target_folder})
        with open(index_html, "w") as fp:
            stream.dump(fp)
        for template_file in (HERE / "templates").iterdir():
            register_dependency(str(template_file))


@dataclass
class TargetImageHandler(FileHandler):
    album: "Album"

    def maybe_target_image(self, target: Stamp) -> Optional[TargetImage]:
        return self.album.target_root.path_to_image(Path(target))

    def target_image(self, target: Stamp) -> TargetImage:
        maybe_target_image = self.maybe_target_image(target)
        assert maybe_target_image
        return maybe_target_image

    def can_handle(self, target: Stamp) -> bool:
        return self.maybe_target_image(target) is not None

    def stamp(self, target: Stamp) -> Stamp:
        image = self.target_image(target)
        return f"{super().stamp(image.path)}; {super().stamp(image.exif_json_path)}"

    def build_impl(self, target: str, register_dependency: RegisterDependencyCallback):
        image = self.target_image(target)

        shutil.copy(image.source.path, image.path)

        # TODO: create thumbnail images

        with open(image.exif_json_path, "w") as exif_json_fp:
            json.dump(get_exif_tags(image.source.path), exif_json_fp, indent=2)

        register_dependency(str(image.source.path))
        register_dependency(__file__)


@dataclass
class Album(Build):
    source_path: InitVar[Path]
    target_path: InitVar[Path]
    source_root: SourceFolder = field(init=False)
    target_root: TargetFolder = field(init=False)
    env: jinja2.Environment = field(init=False)

    def __post_init__(self, source_path: Path, target_path: Path):
        self.source_root = SourceFolder(source_path)
        self.target_root = TargetFolder(self.source_root, None, target_path)

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
            "root": self.target_root.path,
        }
        self.env.filters["relative_to"] = relative_to
        self.env.filters["to_safe_ascii"] = to_safe_ascii

        self.load_build_db()
        self.handlers.append(TargetFolderHandler(self))
        self.handlers.append(TargetImageHandler(self))
        self.handlers.append(FileHandler())

    def render(self):
        self.build(str(self.target_root.path))
        self.save_build_db()


def main():
    logging.getLogger().setLevel(logging.INFO)
    logging.getLogger().addHandler(logging.StreamHandler())
    parser = argparse.ArgumentParser()
    parser.add_argument("source_path", type=Path)
    parser.add_argument("target_path", type=Path)
    args = parser.parse_args()
    source_path: Path = args.source_path
    target_path: Path = args.target_path
    source_path = source_path.absolute()
    target_path = target_path.absolute()
    album = Album(target_path / "build.db.json", source_path, target_path)
    album.render()


if __name__ == "__main__":
    main()

exiftool.__exit__(None, None, None)
