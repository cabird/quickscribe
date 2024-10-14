import os
import fnmatch
from pathlib import Path

# Read patterns from the .fileinclude file
def read_patterns(filename):
    include_patterns = []
    exclude_patterns = []
    with open(filename, 'r') as f:
        for line in f:
            # Remove comments and empty lines
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            # Handle exclusion with '!' at the beginning
            if line.startswith('!'):
                exclude_patterns.append(line[1:].strip())
            else:
                include_patterns.append(line.strip())
    return include_patterns, exclude_patterns

# Collect files based on include and exclude patterns in the current directory (non-recursive)
def collect_files(include_patterns, exclude_patterns):
    all_files = set()
    current_path = Path('.')

    # Iterate through include patterns and add matching files
    for pattern in include_patterns:
        # Find all files matching the pattern in the current directory
        all_files.update(current_path.glob(pattern))

    # Apply exclusion patterns to remove unwanted files
    for pattern in exclude_patterns:
        all_files = {f for f in all_files if not fnmatch.fnmatch(str(f), pattern)}

    return sorted(map(str, all_files))

# Write the collected files to filelist.txt
def write_filelist(filelist, output_file='filelist.txt'):
    with open(output_file, 'w') as f:
        for file in filelist:
            f.write(f"{file}\n")

# Main function to read .fileinclude and generate filelist.txt
def generate_filelist():
    include_patterns, exclude_patterns = read_patterns('fileinclude')
    print(include_patterns)
    print(exclude_patterns)
    filelist = collect_files(include_patterns, exclude_patterns)
    for file in filelist:
        print(file)
    write_filelist(filelist)
    print(f"{len(filelist)} files written to filelist.txt")

if __name__ == "__main__":
    generate_filelist()
