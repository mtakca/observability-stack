import yaml
import sys
import os
import datetime
import uuid

def add_alert_rule(yaml_content, domain="wallet", base_dir="alert-rules"):
    # 1. Validate YAML syntax
    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        print(f"Error: Invalid YAML syntax. {e}")
        sys.exit(1)

    if not data:
        print("Error: Empty YAML content.")
        sys.exit(1)

    # 2. Validate Structure
    groups = []
    if isinstance(data, dict):
        if 'grafana' in data:
             groups = data.get('grafana', {}).get('alerting', {}).get('rules.yaml', {}).get('groups', [])
        elif 'groups' in data:
             groups = data['groups']
        elif 'name' in data and 'rules' in data:
             groups = [data]
    elif isinstance(data, list):
        groups = data

    if not groups:
        print("Error: No valid alert groups found in the provided YAML.")
        sys.exit(1)

    # 3. Generate Filename
    group_name = groups[0].get('name', 'unknown-group').replace(' ', '-').lower()
    first_rule_uid = "rule"
    if groups[0].get('rules'):
        first_rule_uid = groups[0]['rules'][0].get('uid', 'unknown-uid')
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    
    filename = f"custom-{group_name}-{first_rule_uid}-{timestamp}.yaml"
    
    # Construct path based on domain
    output_dir = os.path.join(base_dir, domain)
    filepath = os.path.join(output_dir, filename)

    # 4. Write to file
    try:
        os.makedirs(output_dir, exist_ok=True)
        with open(filepath, 'w') as f:
            yaml.dump(data, f, sort_keys=False)
        print(f"Successfully saved alert rule to {filepath}")
    except Exception as e:
        print(f"Error writing file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Usage: python add_alert_rule.py <yaml_content_or_file> <domain>
    content = ""
    if len(sys.argv) > 1:
        arg1 = sys.argv[1]
        # Check if argument is a file
        if os.path.isfile(arg1):
            try:
                with open(arg1, 'r') as f:
                    content = f.read()
            except Exception as e:
                print(f"Error reading file {arg1}: {e}")
                sys.exit(1)
        else:
            content = arg1
    else:
        print("Reading YAML content from stdin...")
        content = sys.stdin.read()
    
    domain_arg = "wallet"
    if len(sys.argv) > 2:
        domain_arg = sys.argv[2]

    add_alert_rule(content, domain=domain_arg)
