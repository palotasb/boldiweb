import argparse
import collections
import functools
import json
import logging
import math
import re
import shutil
from dataclasses import InitVar, dataclass, field
from pathlib import Path
from typing import Any, Optional

import jinja2
from exiftool import ExifToolHelper
from PIL import Image
from unidecode import unidecode

from boldibuild import Builder, BuildSystem, FileHandler, Stamp, Target

# source folder -> image list
# image list -> exif db
# exif db -> exif data
# image list + exif db -> output images
# output images + templates -> output html


logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())


IMAGE_EXTENSIONS = (".JPG", ".JPEG", ".PNG", ".GIF")
HERE = Path(__file__).parent.resolve()
NON_URL_SAFE_RE = re.compile(r"[^\w\d\.\-\(\)_/]+", re.ASCII)
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
        for item in sorted(self.path.iterdir()):
            name = item.name
            if name.startswith("."):
                pass
            elif item.is_file() and item.suffix.upper() in IMAGE_EXTENSIONS:
                self.images[name] = SourceImage(item)
            elif item.is_dir():
                self.subfolders[name] = SourceFolder(item)


@dataclass
class TargetImage:
    source: SourceImage
    parent: "TargetFolder"
    path: Path = field(init=False)
    path_3000w: Path = field(init=False)
    path_1500w: Path = field(init=False)
    path_800w: Path = field(init=False)
    exif_path: Path = field(init=False)

    def __post_init__(self):
        self.path = self.parent.path / to_safe_ascii(self.source.path.name)
        self.path_3000w = self.path.with_suffix(f".3000{self.path.suffix}")
        self.path_1500w = self.path.with_suffix(f".1500{self.path.suffix}")
        self.path_800w = self.path.with_suffix(f".800{self.path.suffix}")
        self.exif_path = self.path.with_suffix(f"{self.path.suffix}.exif.json")

    @functools.cached_property
    def exif_data(self) -> dict[str, Any]:
        return json.loads(self.exif_path.read_text())

    @property
    def title(self) -> str:
        return self.exif_data["EXIF"].get("Title") or self.source.path.stem

    @property
    def focal_length(self) -> Optional[str]:
        native_f = self.exif_data["EXIF"].get("FocalLength")
        if native_f is None:
            return None
        else:
            return f"{native_f}"

    @property
    def shutter_speed(self) -> Optional[str]:
        speed_s = float(self.exif_data["EXIF"].get("ShutterSpeedValue", "0.0"))
        if speed_s >= 10.0:
            return f"{round(speed_s, None)}"
        elif speed_s >= 0.5:
            return f"{round(speed_s, 1)}"
        elif speed_s > 0.0:
            return f"1/{round(1/speed_s, None)}"
        else:
            return None


@dataclass
class TargetFolder:
    source: SourceFolder
    parent: Optional["TargetFolder"]
    path: Path = None
    subfolders: dict[str, "TargetFolder"] = field(init=False, default_factory=dict)
    images: dict[str, TargetImage] = field(init=False, default_factory=dict)

    def __post_init__(self):
        self.path = self.path or self.parent.path / to_safe_ascii(self.source.path.name)
        for source_subfolder in self.source.subfolders.values():
            subfolder = TargetFolder(source_subfolder, self)
            self.subfolders[subfolder.path.name] = subfolder
        for source_image in self.source.images.values():
            image = TargetImage(source_image, self)
            self.images[image.path.name] = image

    def path_to_folder(self, path: Path) -> Optional["TargetFolder"]:
        if path == self.path:
            return self
        elif path.is_relative_to(self.path):
            for subfolder in self.subfolders.values():
                if (maybe_subfolder := subfolder.path_to_folder(path)) is not None:
                    return maybe_subfolder

    def path_to_image(self, path: Path) -> Optional[TargetImage]:
        folder = self.path_to_folder(Path(*path.parts[:-1]))
        return folder.images.get(path.name) if folder else None


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

    def rebuild_impl(self, target: Target, builder: Builder):
        target_folder = self.target_folder(target)

        target_folder.path.mkdir(parents=True, exist_ok=True)
        builder.add_source(target_folder.source.path)

        for subfolder in target_folder.subfolders.values():
            builder.build(subfolder.path)

        for image in target_folder.images.values():
            builder.build(image.path)

        index_html = target_folder.path / "index.html"

        index_template = self.album.env.get_template("index.html")
        stream = index_template.stream({"folder": target_folder})
        with open(index_html, "w") as fp:
            stream.dump(fp)
        for template_file in (HERE / "templates").iterdir():
            builder.add_source(template_file)

        builder.add_source(__file__)


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
        return "; ".join(
            FileHandler.stamp(self, path)
            for path in [
                image.path,
                # image.path_3000w,
                # image.path_1500w,
                # image.path_800w,
                image.exif_path,
            ]
        )

    def rebuild_impl(self, target: str, builder: Builder):
        image = self.target_image(target)

        shutil.copy(image.source.path, image.path)

        # with Image.open(image.path) as pil_image:
        #     w, h = 3000, round(3000 / pil_image.size[0] * pil_image.size[1])
        #     with pil_image.resize((w, h)) as resized_image:
        #         resized_image.save(image.path_3000w)
        #     w, h = 1500, round(1500 / pil_image.size[0] * pil_image.size[1])
        #     with pil_image.resize((w, h)) as resized_image:
        #         resized_image.save(image.path_1500w)
        #     w, h = 800, round(800 / pil_image.size[0] * pil_image.size[1])
        #     with pil_image.resize((w, h)) as resized_image:
        #         resized_image.save(image.path_800w)

        with open(image.exif_path, "w") as fp:
            json.dump(get_exif_tags(image.source.path), fp, indent=2)

        builder.add_source(image.source.path)


@dataclass
class Album(BuildSystem):
    source_path: InitVar[Path]
    target_path: InitVar[Path]
    target_root: TargetFolder = field(init=False)
    env: jinja2.Environment = field(init=False)

    def __post_init__(self, source_path: Path, target_path: Path):
        self.target_root = TargetFolder(SourceFolder(source_path), None, target_path)

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
        self.build(self.target_root.path)
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
