env_file = '.env'
example_env_file = 'example.env'

with open(env_file, 'r') as infile, open(example_env_file, 'w') as outfile:
    for line in infile:
        line = line.strip()
        if not line or line.startswith('#'):
            outfile.write(line + '\n')
        elif '=' in line:
            key, value = line.split('=', 1)
            if 'KEY' in key or 'CONNECTION_STRING' in key or 'SECRET' in key or 'ID' in key:
                value = 'REDACTED'
            # if there is a url in the value, replace the first part of the url with <fill in>
            if "http" in value:
                #get from "//" to the first "." and replace with "<fill in>"
                parts = value.split("//")
                parts2 = parts[1].split(".", 1)
                value = parts[0] + "//<fill in>." + parts2[1]
            outfile.write(f"{key}={value}\n")
        else:
            outfile.write(line + '\n')

print(f"example.env generated successfully: {example_env_file}")
