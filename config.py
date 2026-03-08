"""
Gymnasion Configuration Manager - Centralized configuration with validation.
Handles environment variables, type conversions, and default values.
"""
import os
import structlog
from typing import Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path

logger = structlog.get_logger(__name__)


@dataclass
class FirebaseConfig:
    """Firebase configuration with validation"""
    credentials_path: Path
    project_id: str
    
    def __post_init__(self):
        if not self.credentials_path.exists():
            logger.error("Firebase credentials file not found", path=str(self.credentials_path))
            raise FileNotFoundError(f"Firebase credentials not found at {self.credentials_path}")
        
        if not self.project_id:
            logger.error("Firebase project ID is required")
            raise ValueError("Firebase project ID is required")


@dataclass
class SystemConfig:
    """System runtime configuration"""
    initial_pod_count: int
    auction_interval_minutes: int
    evolution_interval_hours: int
    max_epoch_seconds: int
    historical_data_path: Path
    synthetic_data_seed: int
    
    def __post_init__(self):
        if self.initial_pod_count < 1:
            logger.warning("Initial pod count too low, setting to minimum 1")
            self.initial_pod_count = 1
            
        if not self.historical_data_path.exists():
            logger.warning("Historical data file not found, synthetic-only mode will be used")
            # Don't raise - we can operate in synthetic-only mode


@dataclass
class AlertConfig:
    """Alerting configuration"""
    telegram_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None


class GymnasionConfig:
    """Main configuration manager"""
    
    def __init__(self):
        self._load_config()
        logger.info("Configuration loaded successfully")
    
    def _load_config(self) -> None:
        """Load and validate all configuration"""
        # Firebase
        creds_path = Path(os.getenv("FIREBASE_CREDENTIALS_PATH", "./firebase-key.json"))
        self.firebase = FirebaseConfig(
            credentials_path=creds_path,
            project_id=os.getenv("FIREBASE_PROJECT_ID", "gymnasion-forge")
        )
        
        # System
        self.system = SystemConfig(
            initial_pod_count=int(os.getenv("INITIAL_POD_COUNT", "5")),
            auction_interval_minutes=int(os.getenv("RESOURCE_AUCTION_INTERVAL_MINUTES", "10")),
            evolution_interval_hours=int(os.getenv("EVOLUTION_CYCLE_INTERVAL_HOURS", "1")),
            max_epoch_seconds=int(os.getenv("MAX_EPOCH_DURATION_SECONDS", "86400")),
            historical_data_path=Path(os.getenv("HISTORICAL_DATA_PATH", "./data/historical.parquet")),
            synthetic_data_seed=int(os.getenv("SYNTHETIC_DATA_SEED", "42"))
        )
        
        # Alerting
        self.alert = AlertConfig(
            telegram_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID")
        )
        
        # Verify critical paths
        self._verify_data_directory()
    
    def _verify_data_directory(self) -> None:
        """Ensure data directory exists"""
        data_dir = self.system.historical_data_path.parent
        data_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Data directory verified", path=str(data_dir))


# Global configuration instance
config = GymnasionConfig()