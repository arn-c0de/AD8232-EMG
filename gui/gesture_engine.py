import json
import numpy as np


class GestureEngine:
    """Multi-channel RMS nearest-neighbour gesture classifier."""

    def __init__(self) -> None:
        self.templates: dict[str, np.ndarray] = {}
        self.last_prediction = "RELAXED"

    # ── template management ──────────────────────────────────────────────────

    def record_template(self, label: str, rms_samples: list[list[float]]) -> None:
        """Average per-channel sample lists into a single feature vector."""
        vector = np.array([
            float(np.mean(ch)) if ch else 0.0
            for ch in rms_samples
        ])
        self.templates[label] = vector

    def delete_template(self, label: str) -> None:
        self.templates.pop(label, None)

    def get_labels(self) -> list[str]:
        return list(self.templates.keys())

    # ── classification ───────────────────────────────────────────────────────

    def classify(self, current_rms: list[float]) -> str:
        """Return label of nearest template, or 'NO TEMPLATES'."""
        if not self.templates:
            return "NO TEMPLATES"
        vec = np.array(current_rms, dtype=float)
        best_label = "UNKNOWN"
        best_dist = float("inf")
        for label, tmpl in self.templates.items():
            n = min(len(vec), len(tmpl))
            d = float(np.linalg.norm(vec[:n] - tmpl[:n]))
            if d < best_dist:
                best_dist = d
                best_label = label
        self.last_prediction = best_label
        return best_label

    # ── persistence ──────────────────────────────────────────────────────────

    def save(self, path: str) -> None:
        data = {k: v.tolist() for k, v in self.templates.items()}
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, path: str) -> None:
        with open(path) as f:
            data = json.load(f)
        self.templates = {k: np.array(v, dtype=float) for k, v in data.items()}
