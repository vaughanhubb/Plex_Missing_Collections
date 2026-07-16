
import json

class ConfigManager:
    def __init__(self, config_path='config.json'):
        self.config_path = config_path

    def load_config(self):
        with open(self.config_path, 'r') as f:
            return json.load(f)

    def save_config(self, config):
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)
    
    def set_config(self, config):
        with open(self.config_path, 'w') as f:
            json.dump(config, f, indent=2)
            
    @staticmethod
    def get_config(config_path='config.json'):
        # Load plain JSON config directly
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "plex_token": "",
                "server_url": "http://localhost:32400",
                "tmdb_api_key": ""
            }

