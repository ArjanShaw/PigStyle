#!/usr/bin/env python3
import subprocess
import os
import sys
from datetime import datetime
from pathlib import Path

def run_command(cmd, cwd=None):
    """Run a shell command and return result"""
    try:
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
        print(f"Return code: {result.returncode}")
        if result.stdout:
            print(f"STDOUT: {result.stdout}")
        if result.stderr:
            print(f"STDERR: {result.stderr}")
        return result.returncode == 0, result.stdout, result.stderr
    except Exception as e:
        print(f"Command error: {e}")
        return False, "", str(e)

def sync_to_github():
    # Change to repo directory
    repo_path = Path("/home/arjan-ubuntu/Documents/PigStyle")
    print(f"📁 Repository path: {repo_path}")
    
    if not repo_path.exists():
        print("❌ Repository path does not exist!")
        return False
    
    os.chdir(repo_path)
    print(f"📂 Current directory: {os.getcwd()}")
    
    # Copy the JSON file from web/public to the root so it's accessible at pigstylerecords.com/gallery-data.json
    source_json = repo_path / "web" / "public" / "gallery-data.json"
    target_json = repo_path / "gallery-data.json"
    
    print(f"📄 Source JSON: {source_json}")
    print(f"🎯 Target JSON: {target_json}")
    
    if not source_json.exists():
        print("❌ Source JSON file not found in web/public/!")
        return False
    
    # Copy the file to root
    import shutil
    shutil.copy2(source_json, target_json)
    print("✅ Copied JSON file to root directory")
    
    try:
        # Git operations - add both locations
        print("🔄 Starting git operations...")
        
        # Add both JSON files
        success, stdout, stderr = run_command(['git', 'add', 'gallery-data.json', 'web/public/gallery-data.json'])
        if not success:
            print("❌ Git add failed")
            return False
        print("✅ JSON files staged")
        
        # Check if there are actually changes to commit
        success, stdout, stderr = run_command(['git', 'status', '--porcelain'])
        if not stdout.strip():
            print("ℹ️ No changes to commit (files unchanged)")
            return True
        
        # Commit with a descriptive message
        commit_msg = f"Update gallery data - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        success, stdout, stderr = run_command(['git', 'commit', '-m', commit_msg])
        
        if not success:
            print("❌ Git commit failed")
            return False
        
        print("✅ Changes committed")
        
        # Push to GitHub
        print("🚀 Pushing to GitHub...")
        success, stdout, stderr = run_command(['git', 'push'])
        if not success:
            print("❌ Git push failed")
            return False
        
        print("✅ Successfully pushed to GitHub!")
        return True
        
    except Exception as e:
        print(f"❌ Sync failed with exception: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return False

if __name__ == "__main__":
    print("🚀 Starting GitHub sync...")
    success = sync_to_github()
    if success:
        print("🎉 GitHub sync completed successfully!")
        sys.exit(0)
    else:
        print("💥 GitHub sync failed!")
        sys.exit(1)