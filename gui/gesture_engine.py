import collections
import numpy as np

class GestureEngine:
    """Combines multi-channel RMS streams to classify gestures."""
    def __init__(self):
        self.templates = {} # label: np.array([mean_rms_ch0, mean_rms_ch1, ...])
        self.last_prediction = "RELAXED"

    def record_template(self, label: str, rms_data: list[list[float]]):
        """Calculates mean vector from recent RMS buffers."""
        vector = np.array([np.mean(ch_buf) for ch_buf in rms_data])
        self.templates[label] = vector

    def classify(self, current_rms_values: list[float]) -> str:
        if not self.templates:
            return "NO TEMPLATES"
        
        current_vec = np.array(current_rms_values)
        min_dist = float('inf')
        prediction = "UNKNOWN"
        
        for label, template in self.templates.items():
            dist = np.linalg.norm(current_vec - template)
            if dist < min_dist:
                min_dist = dist
                prediction = label
                
        self.last_prediction = prediction
        return prediction
