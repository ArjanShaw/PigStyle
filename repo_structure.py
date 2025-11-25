import os
import argparse
from pathlib import Path

def create_repo_dump(target_folder=None, output_file='REPO_STRUCTURE_AND_CODE.txt'):
    """Create ONE file with full repo structure and code from specified folder"""
    
    # If no target folder provided, use current directory
    if target_folder is None:
        target_folder = '.'
    
    # Validate target folder exists
    if not os.path.exists(target_folder):
        print(f"❌ Target folder '{target_folder}' not found!")
        return
    
    print(f"🎯 Processing folder: {target_folder}")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        # Write header
        f.write(f"REPOSITORY STRUCTURE + CODE FROM: {target_folder}\n")
        f.write("=" * 70 + "\n\n")
        
        # Build and write directory tree
        f.write("REPOSITORY STRUCTURE:\n")
        f.write("-" * 40 + "\n")
        
        def build_tree(dir_path, prefix='', is_last=True):
            lines = []
            path_obj = Path(dir_path)
            
            # Skip system directories
            skip_dirs = ['.git', '__pycache__', 'venv', 'env', 'node_modules']
            if any(part in skip_dirs for part in path_obj.parts):
                return lines
            
            # Current directory
            current_prefix = '└── ' if is_last else '├── '
            dir_name = path_obj.name + '/'
            
            # Highlight the target folder
            if str(path_obj) == target_folder or target_folder == '.':
                dir_name = f"🎯 {dir_name} [TARGET]"
            
            lines.append(prefix + current_prefix + dir_name)
            
            # Update prefix for children
            new_prefix = prefix + ('    ' if is_last else '│   ')
            
            try:
                items = []
                for item in os.listdir(dir_path):
                    item_path = os.path.join(dir_path, item)
                    # Skip system files/dirs
                    if not any(skip in item_path for skip in skip_dirs):
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
                        
                        # Highlight code files
                        code_extensions = ['.py', '.html', '.css', '.js', '.json', '.txt', '.md', '.yaml', '.yml']
                        file_ext = os.path.splitext(file_display)[1].lower()
                        
                        if file_ext in code_extensions:
                            icons = {
                                '.py': '🐍', '.html': '🌐', '.css': '🎨', 
                                '.js': '📜', '.json': '📋', '.txt': '📄',
                                '.md': '📖', '.yaml': '⚙️', '.yml': '⚙️'
                            }
                            file_icon = icons.get(file_ext, '📄')
                            file_display = f"{file_display} {file_icon}"
                        
                        lines.append(new_prefix + file_prefix + file_display)
                        
            except PermissionError:
                lines.append(new_prefix + '└── [Permission Denied]')
            
            return lines
        
        # Write the complete tree structure
        tree_lines = build_tree(target_folder if target_folder != '.' else '.')
        f.write("\n".join(tree_lines))
        f.write("\n\n" + "=" * 70 + "\n\n")
        
        # Process the target folder
        total_files_found = 0
        
        f.write(f"CODE FROM: {target_folder}\n")
        f.write("=" * 70 + "\n\n")
        
        # File extensions to include
        code_extensions = ['.py', '.html', '.css', '.js', '.json', '.txt', '.md', '.yaml', '.yml']
        
        # Walk through the target folder
        for root, dirs, files in os.walk(target_folder):
            # Skip system directories
            skip_dirs = ['__pycache__', '.git', 'venv', 'env', 'node_modules']
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            
            for file in files:
                # Include code files
                if any(file.endswith(ext) for ext in code_extensions):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as code_file:
                            content = code_file.read()
                        
                        relative_path = os.path.relpath(file_path, '.')
                        f.write(f"FILE: {relative_path}\n")
                        f.write("-" * 50 + "\n")
                        f.write(content)
                        f.write("\n\n" + "=" * 70 + "\n\n")
                        
                        total_files_found += 1
                        print(f"✅ Added: {relative_path}")
                        
                    except Exception as e:
                        f.write(f"FILE: {file_path} - ERROR: {e}\n")
                        f.write("=" * 70 + "\n\n")
        
        f.write(f"📊 Total files processed: {total_files_found}\n\n")
        
        if total_files_found == 0:
            f.write(f"No code files found in {target_folder}!\n\n")
    
    print(f"\n🎯 DONE: {output_file}")
    print(f"📊 Total code files: {total_files_found}")
    
    # Show file size
    size = os.path.getsize(output_file)
    print(f"📏 Output size: {size} bytes ({size/1024:.1f} KB)")

def main():
    parser = argparse.ArgumentParser(description='Create repository structure and code dump')
    parser.add_argument('folder', nargs='?', default='.', 
                       help='Target folder to extract (default: current directory)')
    parser.add_argument('-o', '--output', default='REPO_STRUCTURE_AND_CODE.txt',
                       help='Output filename (default: REPO_STRUCTURE_AND_CODE.txt)')
    
    args = parser.parse_args()
    
    create_repo_dump(args.folder, args.output)

# RUN IT
if __name__ == "__main__":
    main()