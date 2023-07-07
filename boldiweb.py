import argparse
from dataclasses import dataclass, field
from pathlib import Path

import jinja2

IMAGE_EXTENSIONS = (".JPG", ".JPEG", ".PNG", ".GIF")
HERE = Path(__file__).parent.resolve()


@dataclass(eq=True, order=True, frozen=True)
class Image:
    path: Path


@dataclass(eq=True, order=True, frozen=True)
class Folder:
    path: Path
    subfolders: list["Folder"] = field(default_factory=list, init=False)
    images: list[Image] = field(default_factory=list, init=False)
    ignored_items: list[Path] = field(default_factory=list, init=False)

    def __post_init__(self):
        for item in sorted(self.path.iterdir()):
            if (
                item.is_file()
                and item.suffix.upper() in IMAGE_EXTENSIONS
                and not item.name.startswith(".")
            ):
                self.images.append(Image(item))
            elif item.is_dir() and not item.name.startswith("."):
                self.subfolders.append(Folder(item))
            else:
                self.ignored_items.append(item)

    def __hash__(self) -> int:
        return hash(self.path)


@dataclass(eq=True, order=True, frozen=True)
class PathInfo:
    abs_path: Path
    rel_path: Path
    rev_path: Path

    @staticmethod
    def from_root(root_path: Path, abs_path: Path) -> "PathInfo":
        rel_path = abs_path.relative_to(root_path)
        rev_path = Path(*(Path("..") for _ in rel_path.parts))
        return PathInfo(abs_path, rel_path, rev_path)


@dataclass
class Album:
    root_folder: Folder
    target: Path
    folder_infos: dict[Path, PathInfo] = field(init=False, default_factory=dict)
    image_infos: dict[Path, PathInfo] = field(init=False, default_factory=dict)
    env: jinja2.Environment = field(init=False)
    index_template: jinja2.Template = field(init=False)

    def __post_init__(self):
        self._set_infos(self.root_folder)
        self.env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(HERE / "templates"),
            autoescape=True,
            block_start_string="<j2:block>",
            block_end_string="</j2:block>",
            variable_start_string="<j2:var>",
            variable_end_string="</j2:var>",
            comment_start_string="<j2:comment>",
            comment_end_string="</j2:comment>",
            line_statement_prefix="<j2:line />",
            line_comment_prefix="<j2:linecomment />",
            keep_trailing_newline=True,
        )
        self.env.globals = {
            "album": self,
            "folder_infos": self.folder_infos,
            "image_infos": self.image_infos,
            "target": self.target,
        }
        self.index_template = self.env.get_template("index.html")

    def _set_infos(self, folder: Folder):
        self.folder_infos[folder] = PathInfo.from_root(self.root_folder.path, folder.path)
        for image in folder.images:
            self.image_infos[image] = PathInfo.from_root(self.root_folder.path, image.path)
        for subfolder in folder.subfolders:
            self._set_infos(subfolder)

    def render(self):
        self.render_folder(self.root_folder)

    def render_folder(self, folder: Folder):
        folder_info = self.folder_infos[folder]
        stream = self.index_template.stream(
            {
                "folder": folder,
                "folder_info": folder_info,
            }
        )
        target_path = self.target / folder_info.rel_path / "index.html"
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
    album = Album(Folder(root_path), output_path)
    album.render()


if __name__ == "__main__":
    main()
