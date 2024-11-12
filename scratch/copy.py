#!/usr/bin/env python3
import sys
import subprocess

def copy_files_to_clipboard(file_paths):
    content = ""
    
    # Read content of each file and concatenate
    for file_path in file_paths:
        content += "FILE: " + file_path + "\n\n"
        try:
            with open(file_path, 'r') as file:
                content += file.read() + "\n"
        except FileNotFoundError:
            print(f"Error: {file_path} not found.")
            return
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            return
        content += "\n\n************************************************************\n\n"
    
    # Use clip.exe to copy to Windows clipboard
    process = subprocess.Popen(
        "clip.exe",
        stdin=subprocess.PIPE,
        shell=True
    )
    process.communicate(input=content.encode('utf-8'))

    print("Content copied to Windows clipboard.")

# Check if files were provided
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python wsl_to_clipboard.py file1 [file2 ...]")
    else:
        copy_files_to_clipboard(sys.argv[1:])
