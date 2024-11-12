import json
import sys

# Load the original schema
with open(sys.argv[1], 'r') as f:
    original_schema = json.load(f)

# Function to convert the original schema to the new schema format
def convert_schema(original_schema):
    new_schema = {}

    for filepath, file_info in original_schema.items():
        # Create a simplified structure
        new_schema[filepath] = {
            "type": file_info.get("file_type"),
            "purpose": file_info.get("purpose"),
            "elements": []
        }

        # Add core elements (classes, functions, structures)
        core_elements = file_info.get("core_elements", {})
        
        for cls in core_elements.get("classes", []):
            new_schema[filepath]["elements"].append(f"Class:{cls['name']} - {cls['description']}")
        
        for func in core_elements.get("functions", []):
            new_schema[filepath]["elements"].append(f"Func:{func['name']} - {func['description']}")
        
        for struct in core_elements.get("structures", []):
            new_schema[filepath]["elements"].append(f"Structure:{struct['name']} - {struct['description']}")
        
        # Add dependencies if available
        deps = file_info.get("dependencies", [])
        if deps:
            new_schema[filepath]["deps"] = deps
        
        # Add related files if available
        related = [rel["file"] + " - " + rel["relationship"] for rel in file_info.get("related_files", [])]
        if related:
            new_schema[filepath]["related"] = related
        
        new_schema[filepath]["md5sum"] = file_info["md5sum"]

    return new_schema

# Convert the schema
new_schema = convert_schema(original_schema)

# Save the new schema to a file
with open(sys.argv[2], 'w') as f:
    json.dump(new_schema, f, indent=2)

print("Schema conversion completed. Check 'converted_schema.json' for the new format.")

