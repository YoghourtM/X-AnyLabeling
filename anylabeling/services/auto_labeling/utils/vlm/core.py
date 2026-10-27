"""Prompt, response schema and parsing for direct VLM annotation.

The VLM is asked for every instance of the requested classes and returns
coordinates as integers normalized to ``0..COORD_SCALE`` so the same prompt
works for any image size and any provider.
"""

import json
import math
import re
from dataclasses import dataclass, field

COORD_SCALE = 1000
DEFAULT_MAX_VERTICES = 40

RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["objects"],
    "properties": {
        "objects": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["label", "bbox", "polygon", "confidence"],
                "properties": {
                    "label": {"type": "string"},
                    "bbox": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 4,
                        "maxItems": 4,
                    },
                    "polygon": {
                        "type": "array",
                        "items": {
                            "type": "array",
                            "items": {"type": "integer"},
                            "minItems": 2,
                            "maxItems": 2,
                        },
                    },
                    "confidence": {"type": "number"},
                },
            },
        }
    },
}

PROMPT_TEMPLATE = """You are a precise image annotation engine for segmentation datasets.
Find EVERY visible instance of the target classes in the attached image and outline each one.

Target classes (use these exact label strings):
{classes}

Coordinates: integers normalized to 0-{scale}. x = round({scale} * pixel_x / image_width),
y = round({scale} * pixel_y / image_height). (0,0) is the top-left corner and ({scale},{scale})
the bottom-right corner. The image is {width}x{height} pixels.

For each instance return:
- label: one of the target class strings above
- bbox: [x_min, y_min, x_max, y_max], a tight box around the visible part
- polygon: vertices tracing the visible outer boundary in order (clockwise), 4-{max_vertices} points,
  as tight as possible; put vertices on corners and follow curves; exclude background
- confidence: 0-1

Rules: one entry per distinct instance; a continuous strip or patch is one instance,
clearly separated regions are separate instances. Skip fully occluded instances.
If nothing matches, return {{"objects": []}}. Use only the image pixels, do not call
tools, and return only the JSON object matching the schema.{instructions}"""

_CLASS_SEPARATORS = re.compile(r"[;\n；]+")
_NAME_SEPARATORS = re.compile(r"[,，]+")


@dataclass(frozen=True)
class ClassSpec:
    name: str
    description: str = ""


@dataclass
class Detection:
    label: str
    bbox: tuple  # pixel x0, y0, x1, y1
    polygon: list = field(default_factory=list)  # pixel [(x, y), ...]
    confidence: float | None = None


def parse_class_prompt(text):
    """Parse the user's class prompt.

    ``a, b, c`` lists names; ``name: description`` entries are separated by
    ``;`` or newlines so descriptions may themselves contain commas.
    """
    classes = []
    seen = set()
    for chunk in _CLASS_SEPARATORS.split(text or ""):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" in chunk or "：" in chunk:
            name, description = re.split(r"[:：]", chunk, maxsplit=1)
            entries = [(name, description)]
        else:
            entries = [(name, "") for name in _NAME_SEPARATORS.split(chunk)]
        for name, description in entries:
            name = name.strip()
            if name and name.lower() not in seen:
                seen.add(name.lower())
                classes.append(ClassSpec(name, description.strip()))
    return classes


def build_prompt(
    classes,
    width,
    height,
    instructions="",
    max_vertices=DEFAULT_MAX_VERTICES,
):
    lines = "\n".join(
        (
            f"- {spec.name}: {spec.description}"
            if spec.description
            else f"- {spec.name}"
        )
        for spec in classes
    )
    extra = instructions.strip() if instructions else ""
    return PROMPT_TEMPLATE.format(
        classes=lines,
        scale=COORD_SCALE,
        width=width,
        height=height,
        max_vertices=max_vertices,
        instructions=f"\n\nAdditional instructions:\n{extra}" if extra else "",
    )


def extract_json(text):
    """Return the first JSON object in a model reply (tolerates fences)."""
    if isinstance(text, dict):
        return text
    text = (text or "").strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("VLM reply contains no JSON object")
        try:
            value = json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            from json_repair import repair_json

            value = repair_json(text[start : end + 1], return_objects=True)
    if not isinstance(value, dict):
        raise ValueError("VLM reply JSON is not an object")
    return value


def _to_pixel(value, size):
    value = float(value)
    if not math.isfinite(value):
        raise ValueError("non-finite coordinate")
    value = min(max(value, 0.0), float(COORD_SCALE))
    return value / COORD_SCALE * size


def parse_detections(reply, classes, width, height):
    """Convert a VLM reply into pixel-space detections.

    Unknown labels are dropped when classes were given; malformed geometry is
    skipped instead of failing the whole image.
    """
    data = extract_json(reply)
    objects = data.get("objects")
    if not isinstance(objects, list):
        raise ValueError("VLM reply lacks an 'objects' list")
    names = {spec.name.lower(): spec.name for spec in classes}
    detections = []
    for obj in objects:
        if not isinstance(obj, dict):
            continue
        label = str(obj.get("label", "")).strip()
        if names:
            label = names.get(label.lower())
            if label is None:
                continue
        elif not label:
            continue
        polygon = []
        for point in obj.get("polygon") or []:
            try:
                x, y = point
                polygon.append((_to_pixel(x, width), _to_pixel(y, height)))
            except (TypeError, ValueError):
                polygon = []
                break
        deduped = []
        for point in polygon:
            if not deduped or point != deduped[-1]:
                deduped.append(point)
        if len(deduped) > 1 and deduped[0] == deduped[-1]:
            deduped.pop()
        polygon = deduped if len(set(deduped)) >= 3 else []
        bbox = None
        try:
            x0, y0, x1, y1 = obj.get("bbox") or []
            x0, x1 = sorted((_to_pixel(x0, width), _to_pixel(x1, width)))
            y0, y1 = sorted((_to_pixel(y0, height), _to_pixel(y1, height)))
            if x1 > x0 and y1 > y0:
                bbox = (x0, y0, x1, y1)
        except (TypeError, ValueError):
            bbox = None
        if bbox is None and polygon:
            xs = [x for x, _ in polygon]
            ys = [y for _, y in polygon]
            bbox = (min(xs), min(ys), max(xs), max(ys))
        if bbox is None:
            continue
        confidence = obj.get("confidence")
        try:
            confidence = min(max(float(confidence), 0.0), 1.0)
        except (TypeError, ValueError):
            confidence = None
        detections.append(Detection(label, bbox, polygon, confidence))
    return detections
