from __future__ import annotations

import numpy as np

from nocturne.core.pcm_capture import PCMCapture


def test_pcm_capture_returns_spectrum_array_for_visualizer() -> None:
    capture = PCMCapture(max_samples=2048)
    capture.start()

    try:
        samples = capture.read_fft(n=128)
    finally:
        capture.stop()

    assert samples is not None
    assert isinstance(samples, np.ndarray)
    assert samples.ndim == 1
    assert len(samples) > 0
    assert np.isfinite(samples).all()
