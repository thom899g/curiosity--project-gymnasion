"""
Historical Data Bootstrap - Fetches and prepares market data for simulation.
Uses CCXT for exchange data with fallback mechanisms and validation.
"""
import structlog
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, List
from pathlib import Path
import ccxt
from ccxt import ExchangeError

from config import config

logger = structlog.get_logger(__name__)


class DataBootstrapper:
    """Handles historical data acquisition and preparation"""
    
    def __init__(self):
        self.exchange = self._initialize_exchange()
        self.symbol = "BTC/USDT"  # Primary trading pair
        self.timeframe = "1m"  # 1-minute candles
        
    def _initialize_exchange(self):
        """Initialize CCXT exchange with rate limiting"""
        try:
            exchange = ccxt.binance({
                'enableRateLimit': True,
                'rateLimit': 1200,  # Respect exchange rate limits
                'timeout': 30000
            })
            exchange.load_markets()
            logger.info("Exchange initialized", exchange=exchange.name)
            return exchange
            
        except Exception as e:
            logger.error("Failed to initialize exchange", error=str(e))
            raise
    
    def fetch_historical_data(self, days: int = 30) -> pd.DataFrame:
        """
        Fetch historical OHLCV data with retry logic
        
        Args:
            days: Number of days of historical data to fetch
            
        Returns:
            DataFrame with columns: timestamp, open, high, low, close, volume
        """
        since = self.exchange.parse8601(
            (datetime.utcnow() - timedelta(days=days)).isoformat() + 'Z'
        )
        
        all_ohlcv = []
        current_since = since
        
        logger.info("Fetching historical data", days=days, symbol=self.symbol)
        
        while True:
            try:
                ohlcv = self.exchange.fetch_ohlcv(
                    self.symbol,
                    timeframe=self.timeframe,
                    since=current_since,
                    limit=1000
                )
                
                if not ohlcv:
                    logger.info("No more data available")
                    break
                
                all_ohlcv.extend(ohlcv)
                current_since = ohlcv[-1][0] + 1  # Next millisecond
                
                # Respect rate limits
                self.exchange.sleep(self.exchange.rateLimit / 1000)
                
                # Progress logging
                if len(all_ohlcv) % 5000 == 0:
                    logger.info("Progress", candles_fetched=len(all_ohlcv))
                    
            except ExchangeError as e:
                logger.warning("Exchange error, retrying", error=str(e))
                self.exchange.sleep(5000)  # Wait 5 seconds
                continue
            except Exception as e:
                logger.error("Fatal error fetching data", error=str(e))
                break
        
        if not all_ohlcv:
            raise ValueError("No historical data fetched")
        
        df = pd.DataFrame(
            all_ohlcv,
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        
        logger.info("Historical data fetched", 
                   rows=len(df),
                   date_range=f"{df.index[0]} to {df.index[-1]}")
        
        return df
    
    def validate_data(self, df: pd.DataFrame) -> bool:
        """Validate data quality and consistency"""
        checks = []
        
        # Check for missing values
        missing_pct = df.isnull().sum().sum() / df.size * 100
        checks.append(missing_pct < 5)  # Less than 5% missing
        
        # Check for zero or negative prices
        price_cols = ['open', 'high', 'low', 'close']
        valid_prices = (df[price_cols] > 0).all().all()
        checks.append(valid_prices)
        
        # Check for chronological order
        chronological = df.index.is_monotonic_increasing
        checks.append(chronological)
        
        # Check volume consistency
        volume_positive = (df['volume'] >= 0).all()
        checks.append(volume_positive)
        
        all_valid = all(checks)
        
        if not all_valid:
            logger.warning("Data validation issues", 
                          missing_pct=f"{missing_pct:.2f}%",
                          valid_prices=valid_prices,
                          chronological=chronological,
                          volume_positive=volume_positive)
        
        return all_valid
    
    def generate_synthetic_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Generate synthetic features for simulation"""
        # Price-based features
        df['returns'] = df['close'].pct_change()
        df['log_returns'] = np.log(df['close'] / df['close'].shift(1))
        df['volatility'] = df['returns'].rolling(20).std()
        df['volume_ratio'] = df['volume'] / df['volume'].rolling(20).mean()
        
        # Technical indicators (simplified)
        df['sma_20'] = df['close'].rolling(20).mean()
        df['sma_50'] = df['close'].rolling(50).mean()
        df['rsi'] = self._calculate_rsi(df['close'])
        
        # Market regime flags
        df['trend'] = (df['sma_20'] > df['sma_50']).astype(int)
        df['high_vol'] = (df['volatility'] > df['volatility'].quantile(0.75)).astype(int)
        
        # Fill NaN values
        df.fillna(method='ffill', inplace=True)
        df.fillna(method='bfill', inplace=True)
        
        logger.info("Synthetic features generated", features=list(df.columns))
        return df
    
    def _calculate_rsi(self, prices: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index"""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def save_data(self, df: pd.DataFrame) -> None:
        """Save data to parquet format with compression"""
        try:
            output_path = config.system.historical_data_path
            df.to_parquet(
                output_path,
                compression='snappy',
                index=True
            )
            logger.info("Data saved successfully", 
                       path=str(output_path),
                       size_mb=output_path.stat().st_size / (1024*1024))
        except Exception as e:
            logger.error("Failed to save data", error=str(e))
            raise
    
    def bootstrap(self) -> None:
        """Main bootstrap sequence"""
        logger.info("Starting data bootstrap")
        
        try:
            # Fetch historical data
            df = self.fetch_historical_data