import os
import tempfile

import cv2
from PIL import Image
from PyQt6 import QtCore
from PyQt6.QtCore import QCoreApplication

from anylabeling.views.labeling.logger import logger
from anylabeling.views.labeling.shape import Shape
from anylabeling.views.labeling.utils.opencv import qt_img_to_rgb_cv_img

from .model import Model
from .types import AutoLabelingResult
from .utils.vlm import (
    RESPONSE_SCHEMA,
    build_prompt,
    build_provider,
    load_settings,
    parse_class_prompt,
    parse_detections,
)
from .utils.vlm.providers import image_mime_type

# Formats every supported backend accepts without re-encoding.
_SENDABLE_TYPES = {"image/jpeg", "image/png", "image/webp"}


class VLMAnnotator(Model):
    """Label any class directly with a VLM (codex / claude CLI or OpenAI).

    The text prompt lists the classes to annotate; the VLM returns polygons
    and boxes that are used as-is, with no SAM refinement.
    """

    class Meta:
        required_config_names = ["type", "name", "display_name"]
        widgets = [
            "edit_text",
            "button_send",
            "output_label",
            "output_select_combobox",
            "toggle_preserve_existing_annotations",
            "button_vlm_settings",
        ]
        output_modes = {
            "polygon": QCoreApplication.translate("Model", "Polygon"),
            "rectangle": QCoreApplication.translate("Model", "Rectangle"),
        }
        default_output_mode = "polygon"

    def __init__(self, model_config, on_message) -> None:
        super().__init__(model_config, on_message)
        self.replace = True

    def set_auto_labeling_preserve_existing_annotations_state(self, state):
        self.replace = not state

    def _prepare_image(self, image, image_path, workdir, max_side):
        """Return (file sent to the VLM, its size, label-space size).

        The image file is the source of truth whenever it exists: batch runs
        pass the canvas QImage of a *different* image, and X-AnyLabeling
        rewrites EXIF-rotated files on import, so file pixels match labels.
        Small JPEG/PNG/WebP files are sent untouched; anything else is
        re-encoded. Coordinates are normalized, so resizing is safe.
        """
        from_file = bool(image_path and os.path.isfile(image_path))
        if from_file:
            with Image.open(image_path) as opened:
                width, height = opened.size
            if (
                max(width, height) <= max_side
                and image_mime_type(image_path) in _SENDABLE_TYPES
            ):
                return image_path, (width, height), (width, height)
        else:
            width, height = image.width(), image.height()
        rgb = qt_img_to_rgb_cv_img(image, image_path if from_file else None)
        scale = min(1.0, max_side / float(max(width, height)))
        if scale < 1.0:
            rgb = cv2.resize(
                rgb,
                (max(1, round(width * scale)), max(1, round(height * scale))),
                interpolation=cv2.INTER_AREA,
            )
        path = os.path.join(workdir, "image.jpg")
        cv2.imwrite(
            path,
            cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR),
            [cv2.IMWRITE_JPEG_QUALITY, 95],
        )
        return path, (rgb.shape[1], rgb.shape[0]), (width, height)

    def _to_shape(self, detection):
        shape = Shape(
            label=detection.label,
            score=detection.confidence,
            flags={},
        )
        if self.output_mode == "polygon" and detection.polygon:
            for x, y in detection.polygon:
                shape.add_point(QtCore.QPointF(x, y))
            shape.shape_type = "polygon"
        else:
            # VLM boxes are often looser than their own polygon outline.
            if detection.polygon:
                xs = [x for x, _ in detection.polygon]
                ys = [y for _, y in detection.polygon]
                x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
            else:
                x0, y0, x1, y1 = detection.bbox
            for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
                shape.add_point(QtCore.QPointF(x, y))
            shape.shape_type = "rectangle"
        shape.closed = True
        shape.selected = False
        return shape

    def predict_shapes(
        self, image, image_path=None, text_prompt=None, cancel_event=None
    ):
        if image is None and not (image_path and os.path.isfile(image_path)):
            return AutoLabelingResult([], replace=self.replace)
        classes = parse_class_prompt(text_prompt or "")
        if not classes:
            raise ValueError(
                QCoreApplication.translate(
                    "Model",
                    "Enter the classes to label, e.g. 'tactile_paving: "
                    "raised guide tiles; crosswalk'",
                )
            )
        settings = load_settings()
        provider = build_provider(settings)
        with tempfile.TemporaryDirectory(prefix="xal-vlm-") as workdir:
            path, (sent_w, sent_h), (label_w, label_h) = self._prepare_image(
                image,
                image_path,
                workdir,
                int(settings.get("max_image_side", 2048)),
            )
            prompt = build_prompt(
                classes,
                sent_w,
                sent_h,
                instructions=settings.get("instructions", ""),
                max_vertices=int(settings.get("max_vertices", 40)),
            )
            logger.info(
                f"VLM annotator: provider={provider.name}, "
                f"classes={[spec.name for spec in classes]}, "
                f"image={os.path.basename(image_path or '')}"
            )
            reply = provider.annotate(
                path,
                prompt,
                RESPONSE_SCHEMA,
                timeout=float(settings.get("timeout", 600)),
                cancel_event=cancel_event,
            )
        detections = parse_detections(reply, classes, label_w, label_h)
        logger.info(f"VLM annotator: {len(detections)} objects")
        shapes = [self._to_shape(detection) for detection in detections]
        return AutoLabelingResult(shapes, replace=self.replace)

    def unload(self):
        pass
