from pathlib import Path
import json

BASE_DIR = Path(__file__).parent.parent
PASTA_OUTPUT = BASE_DIR / "output"
PASTA_TEMP = BASE_DIR / "temp"

CONFIG_PATH = PASTA_TEMP / "web_config.json"

DEFAULTS = {
    "font_size": 52,
    "subtitle_style": "karaoke",
    "font_family": "fira-sans",
    "highlight_color": "#FFFF32",
    "base_color": "#B4B4B4",
    "shadow_color": "#000000",
    "text_margin_bottom": 180,
    "max_cuts": 5,
    "whisper_model": "parakeet",
    "detect_method": "ia",
    "crop_vertical": True,
    "bg_music_volume": 0.15,
    "resolution": "1080x1920",
    "zoom_dinamico": False,
    "fade_transition": 0.3,
}


class AppState:
    def __init__(self):
        self.processing = False
        self.progress = 0.0
        self.current_step = ""
        self.job_id = None
        self.config = self._load_config()

    def _load_config(self):
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r") as f:
                    saved = json.load(f)
                merged = {**DEFAULTS, **saved}
                return merged
            except Exception:
                pass
        return dict(DEFAULTS)

    def save_config(self):
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    def update_config(self, updates: dict):
        for k, v in updates.items():
            if k in DEFAULTS:
                self.config[k] = v
        self.save_config()

    def reset(self):
        self.processing = False
        self.progress = 0.0
        self.current_step = ""
