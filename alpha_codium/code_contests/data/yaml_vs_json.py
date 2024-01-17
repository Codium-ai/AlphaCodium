import json
import yaml
s1 = 'print("double quote string")'
s2 = "print('single quote string')"
s3 = 'print("""triple quote string""")'
s4 = f"{s1}\n{s2}\n{s3}"

# Create a dictionary with keys as variable names and values as the strings
data = {'s1': s1, 's2': s2, 's3': s3, 's4': s4}

# Convert the dictionary to a JSON-formatted string
json_data = json.dumps(data, indent=2)
print(json_data)

# Convert the dictionary to a YAML-formatted string, with block scalar style
yaml_data = yaml.dump(data, indent=2, default_style='|')
print(yaml_data)

