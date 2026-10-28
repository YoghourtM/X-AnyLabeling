<div align="center">
  <p>
    <a href="https://github.com/CVHub520/X-AnyLabeling/" target="_blank">
      <img alt="X-AnyLabeling" height="200px" src="anylabeling/resources/images/logo.png"></a>
  </p>

[English](README.md) | [简体中文](README_zh-CN.md)

</div>

## About this fork

This fork of [CVHub520/X-AnyLabeling](https://github.com/CVHub520/X-AnyLabeling) adds two auto-labeling modes that need no manual review, plus frames from video links:

- **VLM Annotator**: a vision-language model (local Codex CLI, local Claude CLI, or an OpenAI-compatible relay) draws polygons or rectangles directly for any classes you describe in a text prompt. Batch runs send images concurrently with a TCP-style adaptive window.
- **SAM 3.1** through Remote-Server: text prompts, clicks / a box, and example boxes, served locally by the [X-AnyLabeling-Server fork](https://github.com/YoghourtM/X-AnyLabeling-Server/tree/feat/sam3.1).
- **Open Video URL** (File menu): downloads videos from YouTube, Bilibili and other sites with yt-dlp, optionally only chosen time ranges of each (a links .txt file can plan them), extracts frames into one folder ready for batch labeling, and records each frame's source in `sources.json`.

### Quick start

**Install** (in this repository):

```bash
conda activate x-anylabeling-cu11
pip install -e ".[gpu-cu11,video]"   # video: yt-dlp for Open Video URL
sudo apt install ffmpeg              # extracts frames (Ubuntu)
xanylabeling
```

**Example 1: label any class with a VLM**

1. Open an image folder, press `Ctrl+A` to show the auto-labeling bar, and pick the model **VLM Annotator (Codex / Claude / OpenAI)**.
2. In **VLM Settings**, pick a backend: Codex CLI (default; run `codex login` once in a terminal), Claude CLI, or an OpenAI-compatible relay with its Base URL, API key and model name.
3. Choose **Polygon** or **Rectangle** output, type a prompt and click **Send**:

   ```text
   tactile_paving: raised yellow paving with bars or dots; crosswalk: white zebra stripes; person
   ```

   The label comes before the colon and a description for the model after it; separate entries with semicolons. Plain names work too, e.g. `person, car`.
4. Press `Ctrl+B` to label the whole folder: images are sent concurrently with an adaptive window, and each is saved as soon as it is done.

**Example 2: segment common classes with SAM 3.1**

Start the local service from the [X-AnyLabeling-Server fork](https://github.com/YoghourtM/X-AnyLabeling-Server/tree/feat/sam3.1) (branch `feat/sam3.1`):

```bash
export SAM31_CHECKPOINT=/path/to/sam3.1_multiplex.pt
scripts/sam31_server.sh build    # first time only
scripts/sam31_server.sh start    # ready in about 20 s; run stop afterwards to free the GPU
```

In the auto-labeling bar pick **Remote-Server** with the address `http://127.0.0.1:8000`, then the model **Segment Anything 3.1** and the task **Text prompt**, and type:

```text
person; vehicle: car, truck, bus; tactile_paving: tactile paving, gray tactile paving
```

`vehicle: car, truck, bus` labels whatever the three prompts find as `vehicle`, keeping one shape per object found more than once. The other two tasks are a single object from clicks or a box (Click / box) and objects similar to example boxes (Example boxes).

**Example 3: keep prompts in a .txt file**

Long class lists can live in a .txt file with one entry per line; lines starting with `#` are comments:

```text
# street.txt
person
vehicle: car, truck, bus
tactile_paving: tactile paving, gray tactile paving
```

Click the folder icon to the right of the prompt box to load it; the lines are joined into the box so you can check them before sending. This works for the VLM and SAM 3.1, and in the `Ctrl+B` prompt dialog too.

**Example 4: frames from video links**

Open **File → Open Video URL** and paste links, or click **Load links from file** to pick a .txt file. Each line is a link followed by the time ranges to download:

```text
# plan.txt
https://www.bilibili.com/video/BV1FL4y1g7Pd   0:05-0:08   0:20-0:23   0:35-
https://www.youtube.com/watch?v=aqz-KE-bpKQ   1:00 ~ 1:05, 1:03-1:10
https://www.youtube.com/watch?v=jNQXAC9IVRw   # no time ranges
```

- `0:35-` runs from 0:35 to the end of the video. `~` also works as the dash; separate ranges with spaces, commas or semicolons.
- Overlapping ranges are merged, so the second line downloads `1:00-1:10`. Ranges for a link on several lines are merged too.
- A link without ranges uses the dialog's **Default time range**, or the whole video when that is empty as well.
- Each range is downloaded on its own. If a line has a mistake, nothing starts; the dialog lists the line numbers and what is wrong.
- At 1 frame per second, the first line gives 13 frames, `bilibili_BV1FL4y1g7Pd_t000005.jpg` to `…_t000041.jpg`; the seconds in each name are the moment the frame shows. `sources.json` in the frames folder records which video and second each image came from.

When the frames are done, their folder opens; label it with `Ctrl+B` as in example 1 or 2.

Full guide (every setting, troubleshooting, running a download plan from Python): [docs/en/vlm_annotator.md](./docs/en/vlm_annotator.md) ([中文](./docs/zh_cn/vlm_annotator.md)). The rest of this README is upstream's.

<p align="center">
    <a href="./LICENSE"><img src="https://img.shields.io/badge/License-GPL%20v3-blue.svg"></a>
    <a href="https://github.com/CVHub520/X-AnyLabeling/releases/latest"><img src="https://img.shields.io/github/v/release/CVHub520/X-AnyLabeling?color=ffa"></a>
    <a href="https://pypi.org/project/x-anylabeling-cvhub/"><img src="https://img.shields.io/pypi/v/x-anylabeling-cvhub?logo=pypi&logoColor=white"></a>
    <a href="./pyproject.toml"><img src="https://img.shields.io/badge/python-3.11+-aff.svg"></a>
    <a href="https://github.com/CVHub520/X-AnyLabeling/releases/latest"><img src="https://img.shields.io/badge/os-linux%2C%20win%2C%20mac-pink.svg"></a>
    <a href="https://github.com/CVHub520/X-AnyLabeling/releases"><img src="https://img.shields.io/github/downloads/CVHub520/X-AnyLabeling/total?label=downloads"></a>
    <a href="https://modelscope.cn/collections/X-AnyLabeling-7b0e1798bcda43"><img src="https://img.shields.io/badge/modelscope-X--AnyLabeling-6750FF?link=https%3A%2F%2Fmodelscope.cn%2Fcollections%2FX-AnyLabeling-7b0e1798bcda43"></a>
</p>

<img src="https://github.com/user-attachments/assets/aa819dae-e38c-4b1c-a4a7-53a873d870e3" alt="X-AnyLabeling interface" width="100%" />

<p align="center">
  <a href="https://xanylabeling.com/docs/x-anylabeling/point_cloud" target="_blank"><img src="assets/resources/pointcloud/pointcloud-3d-det.png" alt="3D Point Cloud Detection" width="50%" /></a><a href="https://xanylabeling.com/docs/x-anylabeling/point_cloud" target="_blank"><img src="assets/resources/pointcloud/pointcloud-3d-seg.png" alt="3D Point Cloud Segmentation" width="50%" /></a>
<br />
  <img src="assets/resources/pointcloud/pointcloud-captions-en.svg" alt="Left: 3D Point Cloud Detection; right: 3D Point Cloud Segmentation" width="100%" />
</p>

## 🥳 What's New

- `2026-10-27`: Add square annotation support.
- `2026-10-24`: Add support for smooth zoom, free panning, and boundary clipping on the canvas.
- `2026-10-18`: Add support for [GroundingPI, GroundAnything, and GroundAnything-VLM](./examples/vision_foundation/groundingpi/README.md) with detection, grounding, referring and category-based pointing, OCR, document layout, GUI grounding, and visual prompting.
- `2026-10-01`: Add [3D point cloud annotation](./docs/en/point_cloud.md), supporting 3D point cloud detection and segmentation.
- `2026-08-19`: Add support for [image tagging](https://xanylabeling.com/docs/x-anylabeling/user_guide#37-image-tags), with tag creation, editing, reordering, and batch deletion.
- `2026-08-12`: Add support for [D-FINE-seg](https://github.com/ArgoHA/D-FINE-seg) instance segmentation models.
- `2026-08-08`: Add support for the [RT-DETRv2-OBB](https://xanylabeling.com/examples/detection/obb) rotated object detection model.
- `2026-08-08`: Add the [Magic Wand tool](https://xanylabeling.com/docs/x-anylabeling/user_guide#21-creating-shapes) for quickly creating polygons from contiguous color regions.
- `2026-08-05`: Release [X-AnyLabeling v4.0.0](https://mp.weixin.qq.com/s/RUb8ge-_7br0YeIImuK6YQ).
- For more details, please refer to the [CHANGELOG](./CHANGELOG.md)

## Introduction

**X-AnyLabeling** is a lightweight, efficient, and unified cross-platform desktop application for AI-assisted annotation of text, image, video, point cloud, and multimodal data. It combines versatile built-in tools, automated labeling workflows, state-of-the-art deep learning models, and flexible multi-format import and export. For remote inference, [X-AnyLabeling-Server](https://github.com/CVHub520/X-AnyLabeling-Server) provides a lightweight, extensible backend for connecting custom models and compute resources.

## Key Features

<img src="https://github.com/user-attachments/assets/2925bc88-e22b-4e81-873c-45fd85164f6b" width="100%" />

* Unified support for annotating and processing text, image, video, point cloud, and multimodal data.
* Covers tasks such as 2D image classification, object detection, instance segmentation, pose estimation, oriented object detection, multi-object tracking, optical character recognition, lane annotation, image captioning, visual question answering, document parsing, and 3D point clouds.
* Provides polygons, rectangles, cuboids, rotated boxes, quadrilaterals, circles, lines, polylines, points, masks, and task-specific tools for text detection, text recognition, and KIE.
* Integrates a wide range of state-of-the-art deep learning models for AI-assisted annotation, automated labeling, and batch dataset prediction.
* Supports both local and remote inference through engines and serving frameworks such as `ONNX Runtime`, `TensorRT`, `OpenCV DNN`, `vLLM`, and `SGLang`.
* Supports importing and exporting formats such as `COCO`, `VOC`, `YOLO`, `DOTA`, `MOT`, `MASK`, `PPOCR`, `MMGD`, `VLM-R1`, and `ShareGPT`.
* Runs on Windows, Linux, and macOS, with interfaces available in English, Simplified Chinese, Japanese, and Korean.
* Supports custom model integration, flexible extension, and secondary development.

## Model library

| **Task Category** | **Supported Models** |
| :--- | :--- |
| 🖼️ Image Classification | YOLOv5-Cls, YOLOv8-Cls, YOLO11-Cls, InternImage, PULC |
| 🎯 Object Detection | YOLOv5/6/7/8/9/10, YOLO11/12/26, YOLOX, YOLO-NAS, D-FINE, DAMO-YOLO, Gold_YOLO, RT-DETR, RF-DETR, DEIMv2 |
| 🖌️ Instance Segmentation | YOLOv5-Seg, YOLOv8-Seg, YOLO11-Seg, YOLO26-Seg, Hyper-YOLO-Seg, RF-DETR-Seg, D-FINE-seg |
| 🎨 Semantic Segmentation | U-Net |
| 🏃 Pose Estimation | YOLOv8-Pose, YOLO11-Pose, YOLO26-Pose, DWPose, RTMO |
| 😀 Face Estimation | SCRFD, YOLOv6Lite-Face |
| 👣 Tracking | TrackTrack, Bot-SORT, ByteTrack, SAM2/3-Video |
| 🔄 Rotated Object Detection | YOLOv5-Obb, YOLOv8-Obb, YOLO11-Obb, YOLO26-Obb, RT-DETRv2-OBB |
| 📏 Depth Estimation | Depth Anything |
| 🧩 Segment Anything | SAM 1/2/3, SAM-HQ, SAM-Med2D, EdgeSAM, EfficientViT-SAM, MobileSAM |
| ✂️ Image Matting | RMBG 1.4/2.0 |
| 💡 Proposal | UPN |
| 🏷️ Tagging | RAM, RAM++ |
| 📄 OCR | PP-OCRv4, PP-OCRv5, PP-OCRv6 |
| 🧾 Layout Analysis | PP-DocLayoutV3 |
| 📑 Document Parsing | PaddleOCR-VL, PaddleOCR-VL-1.6 |
| 🗣️ Vision Foundation Models | Rex-Omni, Florence2, LocateAnything, GroundingPI, GroundAnything, GroundAnything-VLM |
| 👁️ Vision Language Models | Qwen3-VL, Gemini, ChatGPT, GLM |
| 🛣️ Lane Detection | CLRNet |
| 🔢 Object Counting | CountGD, GeCO, GeCo2 |
| 📍 Grounding | Grounding DINO, YOLO-World, YOLOE, SAM 3 |
| 📚 Other | 👉 [model_zoo](./docs/en/model_zoo.md) 👈 |

## Docs

0. [Remote Inference Service](https://github.com/CVHub520/X-AnyLabeling-Server)
1. [Installation & Quickstart](./docs/en/get_started.md)
2. [Usage](./docs/en/user_guide.md)
3. [Command Line Interface](./docs/en/cli.md)
4. [Customize a model](./docs/en/custom_model.md)
5. [Chatbot](./docs/en/chatbot.md)
6. [VQA](./docs/en/vqa.md)
7. [Image Classifier](./docs/en/image_classifier.md)
8. [Video Classifier](./docs/en/video_classifier.md)
9. [Document Parsing and Intelligent Text Recognition](./docs/en/paddle_ocr.md)
10. [3D Point Cloud Annotation](./docs/en/point_cloud.md)

## Examples

- [Classification](./examples/classification/)
  - [Image-Level](./examples/classification/image-level/README.md)
  - [Shape-Level](./examples/classification/shape-level/README.md)
- [Detection](./examples/detection/)
  - [HBB Object Detection](./examples/detection/hbb/README.md)
  - [OBB Object Detection](./examples/detection/obb/README.md)
- [Segmentation](./examples/segmentation/README.md)
  - [Instance Segmentation](./examples/segmentation/instance_segmentation/)
  - [Binary Semantic Segmentation](./examples/segmentation/binary_semantic_segmentation/)
  - [Multiclass Semantic Segmentation](./examples/segmentation/multiclass_semantic_segmentation/)
- [Description](./examples/description/)
  - [Tagging](./examples/description/tagging/README.md)
  - [Captioning](./examples/description/captioning/README.md)
- [Estimation](./examples/estimation/)
  - [Face Estimation](./examples/estimation/face_estimation/README.md)
  - [Pose Estimation](./examples/estimation/pose_estimation/README.md)
  - [Depth Estimation](./examples/estimation/depth_estimation/README.md)
- [OCR](./examples/optical_character_recognition/)
  - [Text Recognition](./examples/optical_character_recognition/text_recognition/)
  - [Key Information Extraction](./examples/optical_character_recognition/key_information_extraction/README.md)
- [MOT](./examples/multiple_object_tracking/README.md)
  - [Tracking by HBB Object Detection](./examples/multiple_object_tracking/README.md)
  - [Tracking by OBB Object Detection](./examples/multiple_object_tracking/README.md)
  - [Tracking by Instance Segmentation](./examples/multiple_object_tracking/README.md)
  - [Tracking by Pose Estimation](./examples/multiple_object_tracking/README.md)
- [iVOS](./examples/interactive_video_object_segmentation)
  - [SAM2-Video](./examples/interactive_video_object_segmentation/sam2/README.md)
  - [SAM3-Video](./examples/interactive_video_object_segmentation/sam3/README.md)
- [Matting](./examples/matting/)
  - [Image Matting](./examples/matting/image_matting/README.md)
- [Vision Foundation Models](./examples/vision_foundation/)
  - [Rex-Omni](./examples/vision_foundation/rexomni/README.md)
  - [Florence 2](./examples/vision_foundation/florence2/README.md)
  - [LocateAnything](./examples/vision_foundation/locateanything/README.md)
  - [GroundingPI / GroundAnything / GroundAnything-VLM](./examples/vision_foundation/groundingpi/README.md)
- [Counting](./examples/counting/)
  - [GeCo](./examples/counting/geco/README.md)
  - [GeCo2](./examples/counting/geco2/README.md)
- [Grounding](./examples/grounding/)
  - [YOLOE](./examples/grounding/yoloe/README.md)
  - [SAM 3](./examples/grounding/sam3/README.md)
- [Training](./examples/training/)
  - [Ultralytics](./examples/training/ultralytics/README.md)

## Contribute

We believe in open collaboration! **X‑AnyLabeling** continues to grow with the support of the community. Whether you're fixing bugs, improving documentation, or adding new features, your contributions make a real impact.

To get started, please read our [Contributing Guide](./CONTRIBUTING.md) and make sure to agree to the [Contributor License Agreement (CLA)](./CLA.md) before submitting a pull request.

If you find this project helpful, please consider giving it a ⭐️ star! Have questions or suggestions? Open an [issue](https://github.com/CVHub520/X-AnyLabeling/issues) or email us at cv_hub@163.com.

A huge thank you 🙏 to everyone helping to make X‑AnyLabeling better.

## License

This project is licensed under the [GNU General Public License v3.0](./LICENSE). You may use, modify, and redistribute the software, including for commercial purposes, provided that you comply with the terms of the license.

## Sponsor

Your [sponsorship](https://xanylabeling.com/sponsor) supports X-AnyLabeling's feature development, model integration, documentation, and community maintenance.

## Acknowledgement

I extend my heartfelt thanks to the developers and contributors of [AnyLabeling](https://github.com/vietanhdev/anylabeling), [LabelMe](https://github.com/wkentaro/labelme), [LabelImg](https://github.com/tzutalin/labelImg), [roLabelImg](https://github.com/cgvict/roLabelImg), [PPOCRLabel](https://github.com/PFCCLab/PPOCRLabel) and [CVAT](https://github.com/opencv/cvat), whose work has been crucial to the success of this project.

## Citing

If you use this software in your research, please cite it as below:

```
@misc{X-AnyLabeling,
  year = {2023},
  author = {Wei Wang},
  publisher = {Github},
  organization = {CVHub},
  journal = {Github repository},
  title = {X-AnyLabeling: A Unified Desktop Platform for AI-Assisted Data Annotation},
  howpublished = {\url{https://github.com/CVHub520/X-AnyLabeling}}
}
```

<div align="center"><a href="#top">🔝 Back to Top</a></div>
