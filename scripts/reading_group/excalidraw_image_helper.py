from __future__ import annotations

import base64
import hashlib
import mimetypes
import sys
import time
from pathlib import Path
from typing import Optional

from PIL import Image


SKILL_SCRIPTS = Path("/Users/mclemens/.codex/skills/excalidraw-diagrams/scripts")
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

from excalidraw_generator import _base_element, arrow, rectangle, text


def _stamp_frame(element: dict, frame_id: Optional[str]) -> dict:
    if frame_id:
        element["frameId"] = frame_id
    return element


def image_file_id(image_path: Path) -> str:
    return hashlib.sha256(image_path.read_bytes()).hexdigest()


def image_size(image_path: Path) -> tuple[int, int]:
    with Image.open(image_path) as image:
        return image.size


def add_image(
    scene: dict,
    image_path: Path,
    x: float,
    y: float,
    *,
    width: Optional[float] = None,
    height: Optional[float] = None,
    frame_id: Optional[str] = None,
) -> dict:
    image_path = Path(image_path)
    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
    natural_width, natural_height = image_size(image_path)

    if width is None and height is None:
        width = natural_width
        height = natural_height
    elif width is None:
        width = height * natural_width / natural_height
    elif height is None:
        height = width * natural_height / natural_width

    file_id = image_file_id(image_path)
    data_url = (
        f"data:{mime_type};base64,"
        f"{base64.b64encode(image_path.read_bytes()).decode('ascii')}"
    )

    scene.setdefault("files", {})[file_id] = {
        "mimeType": mime_type,
        "id": file_id,
        "dataURL": data_url,
        "created": int(time.time() * 1000),
    }

    element = _base_element(
        "image",
        x,
        y,
        width,
        height,
        stroke_color="transparent",
        bg_color="transparent",
        roughness=0,
    )
    element.update(
        {
            "strokeColor": "transparent",
            "backgroundColor": "transparent",
            "status": "saved",
            "fileId": file_id,
            "scale": [1, 1],
            "crop": None,
        }
    )
    _stamp_frame(element, frame_id)
    scene["elements"].append(element)
    return element


def add_text(
    scene: dict,
    content: str,
    x: float,
    y: float,
    *,
    font_size: int = 16,
    color: str = "black",
    font_family: str = "hand",
    frame_id: Optional[str] = None,
    align: str = "left",
) -> dict:
    element = text(
        x,
        y,
        content,
        font_size=font_size,
        color=color,
        font_family=font_family,
        align=align,
        roughness=0,
    )
    _stamp_frame(element, frame_id)
    scene["elements"].append(element)
    return element


def add_highlight_box(
    scene: dict,
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    color: str = "orange",
    opacity: int = 18,
    frame_id: Optional[str] = None,
) -> dict:
    element = rectangle(
        x,
        y,
        width,
        height,
        color=color,
        rounded=True,
        opacity=opacity,
        roughness=0,
    )
    element["strokeWidth"] = 3
    _stamp_frame(element, frame_id)
    scene["elements"].append(element)
    return element


def add_arrow_label(
    scene: dict,
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
    *,
    label: Optional[str] = None,
    color: str = "orange",
    frame_id: Optional[str] = None,
) -> None:
    for element in arrow(
        start_x,
        start_y,
        end_x,
        end_y,
        color=color,
        label=label,
        routing="orthogonal",
        roughness=1,
        stroke_width=2,
    ):
        _stamp_frame(element, frame_id)
        scene["elements"].append(element)
