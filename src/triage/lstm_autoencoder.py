"""LSTM Autoencoder for sequence anomaly detection (30-day rolling window)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np

from src.config import settings

logger = logging.getLogger(__name__)

# Defer TensorFlow import to avoid slow startup when not needed
_tf = None
_keras = None


def _lazy_import_tf():
    global _tf, _keras
    if _tf is None:
        import tensorflow as tf
        _tf = tf
        _keras = tf.keras
    return _tf, _keras


class LSTMAutoencoder:
    """
    LSTM Autoencoder for detecting sequence-level anomalies in orbital
    time series (30-day rolling window of delta-V / state vector features).

    Input shape: (batch, timesteps, features)
    """

    def __init__(self, timesteps: int = 30, n_features: int = 5, latent_dim: int = 16):
        self.timesteps = timesteps
        self.n_features = n_features
        self.latent_dim = latent_dim
        self.model = None
        self.threshold: float = 0.0

    def build(self) -> None:
        """Construct the encoder-decoder architecture."""
        tf, keras = _lazy_import_tf()

        encoder_input = keras.layers.Input(shape=(self.timesteps, self.n_features))
        x = keras.layers.LSTM(64, return_sequences=True)(encoder_input)
        x = keras.layers.LSTM(self.latent_dim, return_sequences=False)(x)

        # Decoder
        x = keras.layers.RepeatVector(self.timesteps)(x)
        x = keras.layers.LSTM(self.latent_dim, return_sequences=True)(x)
        x = keras.layers.LSTM(64, return_sequences=True)(x)
        decoder_output = keras.layers.TimeDistributed(
            keras.layers.Dense(self.n_features)
        )(x)

        self.model = keras.Model(encoder_input, decoder_output)
        self.model.compile(optimizer="adam", loss="mse")
        logger.info("Built LSTM Autoencoder: timesteps=%d, features=%d", self.timesteps, self.n_features)

    def fit(self, X: np.ndarray, epochs: int = 50, batch_size: int = 32, validation_split: float = 0.1) -> None:
        """Train on normal sequences. Sets threshold at 95th percentile of training loss."""
        if self.model is None:
            self.build()

        self.model.fit(
            X, X,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=validation_split,
            verbose=0,
        )

        # Set threshold from training reconstruction error
        reconstructions = self.model.predict(X, verbose=0)
        mse = np.mean(np.square(X - reconstructions), axis=(1, 2))
        self.threshold = float(np.percentile(mse, 95))
        logger.info("LSTM trained. Threshold (95th pct): %.6f", self.threshold)

    def reconstruction_error(self, X: np.ndarray) -> np.ndarray:
        """Return per-sample reconstruction error."""
        if self.model is None:
            logger.warning("Model not built; returning zeros.")
            return np.zeros(len(X))
        reconstructions = self.model.predict(X, verbose=0)
        return np.mean(np.square(X - reconstructions), axis=(1, 2))

    def score(self, X: np.ndarray) -> np.ndarray:
        """Normalized anomaly score [0, 1] where 1 = most anomalous."""
        errors = self.reconstruction_error(X)
        if self.threshold <= 0:
            return np.zeros(len(X))
        # Normalize relative to threshold
        return np.clip(errors / (self.threshold * 2), 0.0, 1.0)

    def save(self, path: Optional[Path] = None) -> Path:
        path = path or settings.models_dir / "lstm_autoencoder"
        path.parent.mkdir(parents=True, exist_ok=True)
        if self.model:
            self.model.save(str(path))
        logger.info("Saved LSTM Autoencoder to %s", path)
        return path

    def load(self, path: Optional[Path] = None) -> None:
        _, keras = _lazy_import_tf()
        path = path or settings.models_dir / "lstm_autoencoder"
        if not path.exists():
            logger.warning("Model path not found: %s", path)
            return
        self.model = keras.models.load_model(str(path))
        logger.info("Loaded LSTM Autoencoder from %s", path)
