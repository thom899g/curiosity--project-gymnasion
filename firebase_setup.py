"""
Firebase Setup and Initialization - Establishes the decentralized nervous system.
Creates Firestore collections with proper indexing and security rules.
"""
import json
import structlog
from typing import Dict, Any
from pathlib import Path
import firebase_admin
from firebase_admin import credentials, firestore, initialize_app
from google.cloud.firestore_v1 import Client as FirestoreClient

from config import config

logger = structlog.get_logger(__name__)


class FirebaseManager:
    """Manages Firebase connection and Firestore collections"""
    
    def __init__(self):
        self.app = None
        self.db: Optional[FirestoreClient] = None
        self._initialize_firebase()
    
    def _initialize_firebase(self) -> None:
        """Initialize Firebase Admin SDK"""
        try:
            if not firebase_admin._apps:
                cred = credentials.Certificate(str(config.firebase.credentials_path))
                self.app = initialize_app(cred, {
                    'projectId': config.firebase.project_id
                })
                logger.info("Firebase Admin SDK initialized")
            
            self.db = firestore.client()
            self._verify_connection()
            
        except Exception as e:
            logger.error("Firebase initialization failed", error=str(e))
            raise
    
    def _verify_connection(self) -> None:
        """Verify Firestore connection by writing and reading a test document"""
        test_ref = self.db.collection("system_health").document("connection_test")
        
        try:
            test_data = {
                "timestamp": firestore.SERVER_TIMESTAMP,
                "status": "testing"
            }
            test_ref.set(test_data)
            
            # Verify write
            doc = test_ref.get()
            if doc.exists:
                logger.info("Firestore connection verified")
                test_ref.delete()  # Clean up test document
            else:
                raise ConnectionError("Firestore write verification failed")
                
        except Exception as e:
            logger.error("Firestore connection verification failed", error=str(e))
            raise
    
    def initialize_collections(self) -> None:
        """Initialize all required Firestore collections with base documents"""
        collections = {
            "world_pods": {
                "description": "Active simulation pods with state and balances",
                "indexes": ["resilience_score", "compute_credits", "status"]
            },
            "resource_auctions": {
                "description": "Active bids for compute resources",
                "indexes": ["bid_amount", "pod_id", "auction_end"]
            },
            "strategy_dna": {
                "description": "Genetic material of successful strategies",
                "indexes": ["resilience_score", "timestamp", "strategy_hash"]
            },
            "pathogen_pool": {
                "description": "Successful adversarial patterns",
                "indexes": ["effectiveness_score", "timestamp", "type"]
            },
            "system_metrics": {
                "description": "System-wide performance metrics",
                "indexes": ["timestamp", "metric_type"]
            }
        }
        
        for collection_name, metadata in collections.items():
            try:
                # Create a metadata document for each collection
                meta_ref = self.db.collection(collection_name).document("_metadata")
                meta_ref.set({
                    "initialized": firestore.SERVER_TIMESTAMP,
                    **metadata
                }, merge=True)
                logger.info(f"Collection initialized: {collection_name}")
                
            except Exception as e:
                logger.error(f"Failed to initialize collection {collection_name}", error=str(e))
    
    def get_db(self) -> FirestoreClient:
        """Get Firestore client instance"""
        if not self.db:
            raise RuntimeError("Firestore client not initialized")
        return self.db


# Global Firebase manager instance
firebase_manager = FirebaseManager()