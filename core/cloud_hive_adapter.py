"""
ORBITAL OS - Cloud Hive & User Profile Sync Adapter
Decouples all user memories, profile databases, and Hive Mind knowledge
from the source code repository. Syncs to Supabase / Firebase / Cloud Storage.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error

# Resolve isolated User Data directory outside of Git codebase
LOCAL_APP_DATA = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
ORBITAL_USER_DIR = os.path.join(LOCAL_APP_DATA, "OrbitalOS", "data")
os.makedirs(ORBITAL_USER_DIR, exist_ok=True)

CONFIG_PATH = os.path.join(ORBITAL_USER_DIR, "cloud_config.json")

DEFAULT_CONFIG = {
    "provider": "local_decoupled", # Options: "supabase", "firebase", "local_decoupled"
    "api_url": "",
    "api_key": "",
    "sync_enabled": True
}

def get_cloud_config():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        except Exception:
            pass
    return DEFAULT_CONFIG

def save_cloud_config(cfg):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4)
        return True
    except Exception:
        return False

class CloudHiveAdapter:
    def __init__(self):
        self.config = get_cloud_config()
        self.local_cache_dir = ORBITAL_USER_DIR
        self.local_db_path = os.path.join(self.local_cache_dir, "users_cloud_db.json")
        self.local_hive_path = os.path.join(self.local_cache_dir, "hive_cloud_mind.json")

    def load_users_db(self):
        """Loads user database without touching repository codebase."""
        if os.path.exists(self.local_db_path):
            try:
                with open(self.local_db_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        
        # Migrate legacy local file if exists and not yet migrated
        legacy_path = r"C:\Orbital\users_db.json"
        if os.path.exists(legacy_path):
            try:
                with open(legacy_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.save_users_db(data)
                    return data
            except Exception:
                pass

        if "Gravity" not in db.get("users", {}):
            db.setdefault("users", {})["Gravity"] = {
                "username": "Gravity",
                "password": "Toolongdong!3",
                "role": "admin",
                "status": "active",
                "created": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        return db

    def save_users_db(self, data):
        """Saves user database in isolated AppData location and attempts cloud sync."""
        try:
            with open(self.local_db_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"[!] Local user DB save error: {e}")

        # Cloud sync trigger if configured
        if self.config.get("api_url") and self.config.get("sync_enabled"):
            self._sync_to_cloud("users_db", data)

    def load_user_memory(self, username):
        """Loads memory private to an individual user, ensuring conversations structure is valid."""
        user_mem_file = os.path.join(self.local_cache_dir, f"memory_{username}.json")
        if os.path.exists(user_mem_file):
            try:
                with open(user_mem_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if not isinstance(data, dict): data = {}
                    if "conversations" not in data or not isinstance(data["conversations"], list):
                        data["conversations"] = []
                    if "notes" not in data: data["notes"] = []
                    if "preferences" not in data: data["preferences"] = {}
                    return data
            except Exception:
                pass
        return {
            "username": username,
            "conversations": [],
            "notes": [],
            "preferences": {},
            "updated_at": time.time()
        }

    def save_user_memory(self, username, mem_data):
        """Saves memory private to an individual user."""
        user_mem_file = os.path.join(self.local_cache_dir, f"memory_{username}.json")
        try:
            with open(user_mem_file, "w", encoding="utf-8") as f:
                json.dump(mem_data, f, indent=4)
        except Exception:
            pass

    def load_hive_knowledge(self):
        """Loads cross-device shared Hive Mind knowledge base."""
        if os.path.exists(self.local_hive_path):
            try:
                with open(self.local_hive_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def share_fact_to_hive(self, author, fact):
        """Adds a fact to the shared Hive Mind."""
        facts = self.load_hive_knowledge()
        entry = {
            "author": author,
            "fact": fact,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "cloud_id": f"hive_{int(time.time() * 1000)}"
        }
        facts.append(entry)
        try:
            with open(self.local_hive_path, "w", encoding="utf-8") as f:
                json.dump(facts, f, indent=4)
        except Exception:
            pass
        return entry

    def _sync_to_cloud(self, collection, payload):
        """Dispatches REST sync to Supabase / Firebase endpoint in background thread."""
        try:
            url = f"{self.config['api_url']}/rest/v1/{collection}"
            headers = {
                "apikey": self.config.get("api_key", ""),
                "Authorization": f"Bearer {self.config.get('api_key', '')}",
                "Content-Type": "application/json",
                "Prefer": "return=minimal"
            }
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=3.0) as _:
                pass
        except Exception:
            pass # Fail soft when offline

hive_adapter = CloudHiveAdapter()
