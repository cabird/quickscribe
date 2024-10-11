env_file = '.env'
example_env_file = 'example.env'

with open(env_file, 'r') as infile, open(example_env_file, 'w') as outfile:
    for line in infile:
        line = line.strip()
        if not line or line.startswith('#'):
            outfile.write(line + '\n')
        elif '=' in line:
            key, value = line.split('=', 1)
            if 'KEY' in key or 'CONNECTION_STRING' in key:
                value = 'REDACTED'
            outfile.write(f"{key}={value}\n")
        else:
            outfile.write(line + '\n')

print(f"example.env generated successfully: {example_env_file}")
