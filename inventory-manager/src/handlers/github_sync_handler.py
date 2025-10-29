import subprocess
import os
import json
from pathlib import Path
import streamlit as st
from datetime import datetime

class GitHubSyncHandler:
    def __init__(self, repo_path=None, gallery_json_manager=None):
        self.repo_path = Path(repo_path or "/home/arjan-ubuntu/Documents/PigStyle")
        self.gallery_json_manager = gallery_json_manager
        self.sync_script_path = self.repo_path / "sync_to_github.py"
        
    def trigger_sync(self, commit_message=None):
        """Trigger GitHub sync using your existing script"""
        try:
            if commit_message is None:
                commit_message = f"Auto-sync: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            # Ensure gallery JSON is rebuilt first via the manager
            if self.gallery_json_manager:
                rebuild_success = self.gallery_json_manager.trigger_rebuild(async_mode=False)
                if not rebuild_success:
                    return False, "Gallery JSON rebuild failed"
            
            # Run your existing sync script
            if self.sync_script_path.exists():
                result = subprocess.run(
                    ['python3', str(self.sync_script_path)],
                    capture_output=True, 
                    text=True, 
                    timeout=60,
                    cwd=self.repo_path
                )
                
                if result.returncode == 0:
                    return True, "GitHub sync completed successfully"
                else:
                    # Parse the output to get meaningful error message
                    output = result.stdout + result.stderr
                    if "✅" in output:
                        return True, "Sync completed"
                    else:
                        return False, f"Sync script failed: {output}"
            else:
                return False, f"Sync script not found at: {self.sync_script_path}"
                
        except subprocess.TimeoutExpired:
            return False, "GitHub sync timed out"
        except Exception as e:
            return False, f"Sync error: {str(e)}"
    
    def get_sync_status(self):
        """Get current git status"""
        try:
            # Check if there are any changes
            status_result = subprocess.run(
                ['git', 'status', '--porcelain'],
                capture_output=True, 
                text=True, 
                cwd=self.repo_path
            )
            
            has_changes = bool(status_result.stdout.strip())
            
            # Get last commit info
            log_result = subprocess.run(
                ['git', 'log', '-1', '--format=%H %cd %s', '--date=short'],
                capture_output=True, 
                text=True, 
                cwd=self.repo_path
            )
            
            last_commit = log_result.stdout.strip() if log_result.returncode == 0 else "Unknown"
            
            # Check if sync script exists
            script_exists = self.sync_script_path.exists()
            
            return {
                'has_changes': has_changes,
                'last_commit': last_commit,
                'repo_path': str(self.repo_path),
                'script_exists': script_exists,
                'script_path': str(self.sync_script_path)
            }
            
        except Exception as e:
            return {
                'has_changes': False,
                'last_commit': f"Error: {str(e)}",
                'repo_path': str(self.repo_path),
                'script_exists': self.sync_script_path.exists(),
                'script_path': str(self.sync_script_path)
            }
    
    def manual_trigger_with_message(self, message):
        """Manual trigger with custom commit message"""
        try:
            # First rebuild the JSON
            if self.gallery_json_manager:
                self.gallery_json_manager.trigger_rebuild(async_mode=False)
            
            # Then use git commands directly with custom message
            commands = [
                ['git', 'add', 'web/public/gallery-data.json'],
                ['git', 'commit', '-m', message],
                ['git', 'push']
            ]
            
            for cmd in commands:
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.repo_path)
                if result.returncode != 0:
                    if "nothing to commit" not in result.stderr:
                        return False, f"Command failed: {' '.join(cmd)} - {result.stderr}"
            
            return True, f"Manual sync completed: {message}"
            
        except Exception as e:
            return False, f"Manual sync failed: {str(e)}"