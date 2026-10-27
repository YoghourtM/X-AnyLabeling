import os
import logging
from typing import Literal, Optional

logger = logging.getLogger(__name__)

DeviceType = Literal["CPU", "GPU", "AUTO"]
_ort_gpu_libs_preloaded = False


def preload_onnxruntime_gpu_libs(ort_module=None) -> None:
    """Best-effort preload for CUDA/cuDNN libs used by ONNX Runtime."""
    global _ort_gpu_libs_preloaded
    if _ort_gpu_libs_preloaded:
        return

    _ort_gpu_libs_preloaded = True
    try:
        ort = ort_module
        if ort is None:
            import onnxruntime as ort

        preload_dlls = getattr(ort, "preload_dlls", None)
        if preload_dlls is None:
            return

        for directory in (None, ""):
            try:
                preload_dlls(
                    cuda=True,
                    cudnn=True,
                    msvc=False,
                    directory=directory,
                )
            except TypeError:
                preload_dlls()
                return
            except Exception as e:
                logger.debug(
                    "Failed to preload ONNX Runtime GPU libraries "
                    f"from {directory!r}: {e}"
                )
    except Exception as e:
        logger.debug(f"Failed to preload ONNX Runtime GPU libraries: {e}")


class DeviceManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._preferred_device = None
        self._available_providers = None

    def get_device(self) -> str:
        if self._preferred_device:
            return self._preferred_device

        env_device = os.getenv("X_ANYLABELING_DEVICE", "").upper()
        if env_device in ["CPU", "GPU"]:
            logger.info(f"Using device from environment: {env_device}")
            return self._validate_and_set(env_device)

        config_device = self._load_from_config()
        if config_device:
            logger.info(f"Using device from config: {config_device}")
            return self._validate_and_set(config_device)

        return self._auto_detect()

    def _validate_and_set(self, device: str) -> str:
        if device == "GPU" and not self._is_gpu_available():
            logger.warning(
                "GPU requested but not available. Falling back to CPU."
            )
            device = "CPU"

        self._preferred_device = device
        return device

    def _auto_detect(self) -> str:
        if self._is_gpu_available():
            logger.info("GPU detected and available, using GPU")
            self._preferred_device = "GPU"
            return "GPU"

        logger.info("GPU not available, using CPU")
        self._preferred_device = "CPU"
        return "CPU"

    def _is_gpu_available(self) -> bool:
        if self._available_providers is None:
            try:
                import onnxruntime as ort

                preload_onnxruntime_gpu_libs(ort)
                self._available_providers = ort.get_available_providers()
            except Exception as e:
                logger.debug(f"Failed to get ONNX providers: {e}")
                self._available_providers = []

        return "CUDAExecutionProvider" in self._available_providers

    def _load_from_config(self) -> Optional[str]:
        try:
            import yaml
            from anylabeling.config import get_work_directory

            config_path = os.path.join(get_work_directory(), ".xanylabelingrc")
            if os.path.exists(config_path):
                with open(config_path) as f:
                    config = yaml.safe_load(f)
                    if config:
                        device = str(config.get("device", "")).upper()
                        if device in ["CPU", "GPU"]:
                            return device
        except Exception as e:
            logger.debug(f"Failed to load config: {e}")

        return None

    def set_device(self, device: str):
        device = device.upper()
        if device not in ["CPU", "GPU"]:
            raise ValueError(f"Invalid device: {device}")

        self._preferred_device = device
        logger.info(f"Device manually set to: {device}")

    def reset_device_preference(self):
        self._preferred_device = None
        logger.info("Device preference reset to auto")

    def get_available_devices(self) -> list:
        devices = ["CPU"]
        if self._is_gpu_available():
            devices.append("GPU")
        return devices


device_manager = DeviceManager()


def get_preferred_device() -> str:
    return device_manager.get_device()
