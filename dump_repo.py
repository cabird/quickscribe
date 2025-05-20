import os
import sys
import subprocess
import yaml
from typing import List, Set, Dict, Any, Optional
from pathlib import Path


def find_git_root(start_path: str) -> Optional[str]:
    """Find the root directory of the Git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=start_path,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        print("Error: Not a git repository or git command failed.")
        return None


def get_git_tracked_files(repo_root: str) -> List[str]:
    """Get list of all files tracked by Git in the repository."""
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except subprocess.CalledProcessError as e:
        print(f"Error executing git ls-files: {e}")
        return []


def is_path_in_subtree(path: str, subtree_root: str) -> bool:
    """Check if a path is within a specified subtree."""
    real_path = os.path.realpath(path)
    real_subtree = os.path.realpath(subtree_root)
    return real_path == real_subtree or real_path.startswith(real_subtree + os.sep)


def find_config_files(start_dir: str, repo_root: str) -> List[str]:
    """Find all repo2file.cfg files in the directory tree from repo_root to start_dir and in subdirectories."""
    config_files = []
    
    # Find config files in parent directories (from repo_root to start_dir)
    current = os.path.abspath(start_dir)
    repo_abs = os.path.abspath(repo_root)
    
    while is_path_in_subtree(current, repo_abs):
        config_path = os.path.join(current, "repo2file.cfg")
        if os.path.isfile(config_path):
            config_files.append(config_path)
        if current == repo_abs:
            break
        current = os.path.dirname(current)
    
    # Find config files in subdirectories of start_dir
    for root, _, files in os.walk(start_dir):
        if "dump_repo.cfg" in files and root != start_dir:  # Avoid adding the start_dir config again
            config_files.append(os.path.join(root, "dump_repo.cfg"))
    
    return config_files


def parse_config_file(config_path: str) -> Dict[str, Any]:
    """Parse a dump_repo.cfg YAML file."""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f) or {}
        return config
    except Exception as e:
        print(f"Error parsing config file {config_path}: {e}")
        return {}


def merge_configs(config_files: List[str]) -> Dict[str, Any]:
    """Merge multiple config files, with more specific (deeper) configs taking precedence."""
    # Sort configs from repo root to deepest subdirectory
    sorted_configs = sorted(config_files, key=lambda x: len(os.path.abspath(x).split(os.sep)))
    
    merged_config = {
        "include": [],
        "exclude": [],
        "config": {}
    }
    
    for config_path in sorted_configs:
        config = parse_config_file(config_path)
        config_dir = os.path.dirname(config_path)
        
        # Process includes with relative paths
        if "include" in config and isinstance(config["include"], list):
            for pattern in config["include"]:
                merged_config["include"].append((config_dir, pattern))
        
        # Process excludes with relative paths
        if "exclude" in config and isinstance(config["exclude"], list):
            for pattern in config["exclude"]:
                merged_config["exclude"].append((config_dir, pattern))
        
        # Merge other config options, with newer values overriding older ones
        if "config" in config and isinstance(config["config"], dict):
            merged_config["config"].update(config["config"])
    
    return merged_config


def should_include_file(file_path: str, include_patterns: List[tuple], exclude_patterns: List[tuple]) -> bool:
    """Determine if a file should be included based on include/exclude patterns."""
    # Check exclusions first
    for config_dir, pattern in exclude_patterns:
        # Make pattern relative to the config directory
        pattern_path = os.path.normpath(os.path.join(config_dir, pattern))
        
        # Handle directory patterns
        if pattern.endswith('/') or os.path.isdir(pattern_path):
            dir_pattern = pattern[:-1] if pattern.endswith('/') else pattern
            dir_path = os.path.normpath(os.path.join(config_dir, dir_pattern))
            if is_path_in_subtree(file_path, dir_path):
                return False
        # Handle file patterns with wildcards
        elif '*' in pattern or '?' in pattern:
            from fnmatch import fnmatch
            file_name = os.path.basename(file_path)
            if fnmatch(file_name, pattern):
                return False
            # Check if any parent directory matches
            rel_path = os.path.relpath(file_path, config_dir)
            if any(fnmatch(part, pattern) for part in rel_path.split(os.sep)):
                return False
        # Handle exact file matches
        else:
            pattern_path = os.path.normpath(os.path.join(config_dir, pattern))
            if file_path == pattern_path:
                return False
    
    # Now check inclusions for files that aren't already explicitly included
    for config_dir, pattern in include_patterns:
        # Make pattern relative to the config directory
        pattern_path = os.path.normpath(os.path.join(config_dir, pattern))
        
        # Handle directory patterns
        if pattern.endswith('/') or os.path.isdir(pattern_path):
            dir_pattern = pattern[:-1] if pattern.endswith('/') else pattern
            dir_path = os.path.normpath(os.path.join(config_dir, dir_pattern))
            if is_path_in_subtree(file_path, dir_path):
                return True
        # Handle file patterns with wildcards
        elif '*' in pattern or '?' in pattern:
            from fnmatch import fnmatch
            file_name = os.path.basename(file_path)
            if fnmatch(file_name, pattern):
                return True
            # Check if any parent directory matches
            rel_path = os.path.relpath(file_path, config_dir)
            if any(fnmatch(part, pattern) for part in rel_path.split(os.sep)):
                return True
        # Handle exact file matches
        else:
            pattern_path = os.path.normpath(os.path.join(config_dir, pattern))
            if file_path == pattern_path:
                return True
    
    # If neither excluded nor explicitly included, it depends on whether it's a git-tracked file
    # We'll decide this in the main function based on the file source
    return None


def scan_folder(repo_root: str, current_dir: str, output_file: str, config: Dict[str, Any]) -> None:
    """Scan folder and write content to output file."""
    # Get files tracked by git
    git_files = get_git_tracked_files(repo_root)
    git_files_abs = [os.path.join(repo_root, f) for f in git_files]
    
    # Filter to only files in current directory subtree
    files_in_subtree = [f for f in git_files_abs if is_path_in_subtree(f, current_dir)]
    
    # Find additional files in the current directory that might not be in git
    all_files = set()
    for root, _, files in os.walk(current_dir):
        for file in files:
            file_path = os.path.join(root, file)
            all_files.add(file_path)
    
    # Process files based on include/exclude rules
    final_files = []
    
    # Process git files first
    for file_path in files_in_subtree:
        include_decision = should_include_file(file_path, config["include"], config["exclude"])
        if include_decision is False:  # Explicitly excluded
            continue
        final_files.append(file_path)
    
    # Now process all files to find additional includes
    for file_path in all_files:
        if file_path in final_files:
            continue  # Already included
        
        include_decision = should_include_file(file_path, config["include"], config["exclude"])
        if include_decision is True:  # Explicitly included
            final_files.append(file_path)
    
    # Sort files for consistent output
    final_files.sort()
    
    # Write output
    with open(output_file, 'w', encoding=config.get("config", {}).get("encoding", "utf-8")) as out_file:
        # Write the directory structure
        out_file.write("Directory Structure:\n")
        out_file.write("-------------------\n")
        
        # Create a simplified directory tree representation
        tree = create_tree_representation(current_dir, final_files)
        out_file.write(tree)
        out_file.write("\n\n")
        
        out_file.write("File Contents:\n")
        out_file.write("--------------\n")
        
        # Write file contents
        for file_path in final_files:
            rel_path = os.path.relpath(file_path, current_dir)
            print(f"Processing: {rel_path}")
            if not os.path.exists(file_path):
                print(f"File does not exist: {file_path}")
                continue
            
            out_file.write(f"File: {rel_path}\n")
            out_file.write("-" * 50 + "\n")
            
            max_file_size = config.get("config", {}).get("max_file_size", float('inf'))
            
            if os.path.getsize(file_path) > max_file_size:
                out_file.write(f"File too large (exceeded max_file_size of {max_file_size} bytes). Content skipped.\n")
            else:
                try:
                    with open(file_path, 'r', encoding=config.get("config", {}).get("encoding", "utf-8")) as in_file:
                        content = in_file.read()
                        out_file.write(f"Content of {rel_path}:\n")
                        out_file.write(content)
                except Exception as e:
                    print(f"Error reading file {rel_path}: {str(e)}. Skipping.")
                    out_file.write(f"Error reading file: {str(e)}. Content skipped.\n")
            
            out_file.write("\n\n")


def create_tree_representation(base_path: str, files: List[str]) -> str:
    """Create a tree representation of the files."""
    lines = []
    lines.append(f"{os.path.basename(base_path)}/")
    
    # Convert to relative paths and sort
    rel_paths = [os.path.relpath(f, base_path) for f in files]
    rel_paths.sort()
    
    # Build a dictionary representing the directory structure
    tree_dict = {}
    for path in rel_paths:
        parts = path.split(os.sep)
        current = tree_dict
        for i, part in enumerate(parts):
            if i == len(parts) - 1:  # It's a file
                if "__files__" not in current:
                    current["__files__"] = []
                current["__files__"].append(part)
            else:  # It's a directory
                if part not in current:
                    current[part] = {}
                current = current[part]
    
    # Function to recursively print the tree
    def print_tree(node, prefix="", is_last=True, path=""):
        items = []
        
        # Add directories
        dirs = [d for d in node.keys() if d != "__files__"]
        
        # Add files
        files = node.get("__files__", [])
        
        # Combine and sort
        items = [(d, True) for d in sorted(dirs)] + [(f, False) for f in sorted(files)]
        
        for i, (name, is_dir) in enumerate(items):
            is_last_item = i == len(items) - 1
            
            # Print current item
            if is_last:
                new_prefix = prefix + "    "
                connector = "└── "
            else:
                new_prefix = prefix + "│   "
                connector = "├── "
            
            if is_dir:
                tree_lines.append(f"{prefix}{connector}{name}/")
                # Recursively print subdirectory
                print_tree(node[name], new_prefix, is_last_item, os.path.join(path, name))
            else:
                tree_lines.append(f"{prefix}{connector}{name}")
    
    # Print the tree
    tree_lines = []
    print_tree(tree_dict)
    
    return "\n".join(lines + tree_lines)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python script.py [output_file]")
        print("If output_file is not specified, output.txt will be used.")
        sys.exit(1)
    
    # Determine current directory and output file
    current_dir = os.getcwd()
    output_file = sys.argv[1] if len(sys.argv) > 1 else "output.txt"
    
    # Find Git repo root
    repo_root = find_git_root(current_dir)
    if not repo_root:
        print("Error: Not in a Git repository.")
        sys.exit(1)
    
    print(f"Git repository root: {repo_root}")
    print(f"Current directory: {current_dir}")
    
    # Find and parse config files
    config_files = find_config_files(current_dir, repo_root)
    print(f"Found {len(config_files)} config file(s):")
    for cf in config_files:
        print(f"  - {cf}")
    
    # Merge configs
    config = merge_configs(config_files)
    
    # Scan folder and generate output
    scan_folder(repo_root, current_dir, output_file, config)
    print(f"Scan complete. Results written to {output_file}")


if __name__ == "__main__":
    main()