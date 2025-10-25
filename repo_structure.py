import os
from pathlib import Path

def create_repo_dump():
    """Create ONE file with full repo structure and code from inventory-manager/src"""
    target_folder = 'inventory-manager/src'  # Corrected path with dash
    
    output_file = 'REPO_STRUCTURE_AND_CODE.txt'
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # Write header
        f.write(f"COMPLETE REPOSITORY STRUCTURE + CODE FROM: {target_folder}\n")
        f.write("=" * 70 + "\n")
        f.write(f"Target folder for code: {target_folder}\n")
        f.write("=" * 70 + "\n\n")
        
        # Build and write COMPLETE directory tree
        f.write("FULL REPOSITORY STRUCTURE:\n")
        f.write("-" * 40 + "\n")
        
        def build_tree(dir_path, prefix='', is_last=True):
            lines = []
            path_obj = Path(dir_path)
            
            # Skip system directories
            if any(part in ['.git', '__pycache__', 'venv', 'env'] for part in path_obj.parts):
                return lines
            
            # Current directory
            current_prefix = '└── ' if is_last else '├── '
            dir_name = path_obj.name + '/'
            
            # Highlight the target folder
            if str(path_obj) == target_folder:
                dir_name = f"🎯 {dir_name} [TARGET]"
            
            lines.append(prefix + current_prefix + dir_name)
            
            # Update prefix for children
            new_prefix = prefix + ('    ' if is_last else '│   ')
            
            try:
                items = []
                for item in os.listdir(dir_path):
                    item_path = os.path.join(dir_path, item)
                    # Skip system files/dirs
                    if not any(skip in item_path for skip in ['.git', '__pycache__', 'venv', 'env']):
                        items.append(item_path)
                
                # Sort directories first, then files
                items.sort(key=lambda x: (not os.path.isdir(x), x.lower()))
                
                for i, item_path in enumerate(items):
                    is_last_item = i == len(items) - 1
                    
                    if os.path.isdir(item_path):
                        lines.extend(build_tree(item_path, new_prefix, is_last_item))
                    else:
                        file_prefix = '└── ' if is_last_item else '├── '
                        file_display = os.path.basename(item_path)
                        
                        # Highlight Python files in target folder
                        if item_path.endswith('.py'):
                            file_display += " 🐍"
                            if target_folder in item_path:
                                file_display = f"⭐ {file_display}"
                        
                        lines.append(new_prefix + file_prefix + file_display)
                        
            except PermissionError:
                lines.append(new_prefix + '└── [Permission Denied]')
            
            return lines
        
        # Write the complete tree structure
        tree_lines = build_tree('.')
        f.write("\n".join(tree_lines))
        f.write("\n\n" + "=" * 70 + "\n\n")
        
        # Write ONLY Python code from target folder
        f.write(f"PYTHON CODE FROM: {target_folder}\n")
        f.write("=" * 70 + "\n\n")
        
        python_files_found = 0
        
        # Check if target folder exists
        if not os.path.exists(target_folder):
            f.write(f"❌ Target folder '{target_folder}' not found!\n")
            print(f"❌ Target folder '{target_folder}' not found!")
            
            # Show what folders actually exist
            f.write("\nAvailable folders:\n")
            for item in os.listdir('.'):
                if os.path.isdir(item):
                    f.write(f"- {item}/\n")
                    if item == 'inventory-manager':
                        try:
                            for sub_item in os.listdir('inventory-manager'):
                                f.write(f"  └── {sub_item}/\n")
                        except:
                            pass
        else:
            # Walk through ONLY the target folder
            for root, dirs, files in os.walk(target_folder):
                # Skip system directories
                dirs[:] = [d for d in dirs if d not in ['__pycache__']]
                
                for file in files:
                    if file.endswith('.py'):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as py_file:
                                content = py_file.read()
                            
                            relative_path = os.path.relpath(file_path, '.')
                            f.write(f"FILE: {relative_path}\n")
                            f.write("-" * 50 + "\n")
                            f.write(content)
                            f.write("\n\n" + "=" * 70 + "\n\n")
                            
                            python_files_found += 1
                            print(f"✅ Added: {relative_path}")
                            
                        except Exception as e:
                            f.write(f"FILE: {file_path} - ERROR: {e}\n")
                            f.write("=" * 70 + "\n\n")
            
            if python_files_found == 0:
                f.write(f"No Python files found in {target_folder}!\n")
    
    print(f"\n🎯 DONE: {output_file}")
    print(f"📊 Python files from {target_folder}: {python_files_found}")
    
    # Show file size
    size = os.path.getsize(output_file)
    print(f"📏 Output size: {size} bytes ({size/1024:.1f} KB)")

# RUN IT
if __name__ == "__main__":
    create_repo_dump()