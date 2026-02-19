import yaml
import os
import sys
import glob
import re

def sanitize_name(name):
    """Sanitize string to be a valid Kubernetes resource name component."""
    # Lowercase, replace non-alphanumeric with dashes, strip leading/trailing dashes
    s = name.lower()
    s = re.sub(r'[^a-z0-9]', '-', s)
    s = re.sub(r'-+', '-', s)
    return s.strip('-')

def merge_alerts(base_values_file, rules_dir, output_file, names_file=None):
    # Initialize the structure for collecting groups
    all_groups = []

    # 1. Load the base values.alerts.yaml if it exists
    if os.path.exists(base_values_file):
        print(f"Loading base alerts from {base_values_file}...")
        with open(base_values_file, 'r') as f:
            base_data = yaml.safe_load(f)
            # Extract existing groups if the structure matches
            try:
                groups = base_data.get('grafana', {}).get('alerting', {}).get('rules.yaml', {}).get('groups', [])
                if groups:
                    all_groups.extend(groups)
                    print(f"Loaded {len(groups)} groups from base file.")
            except AttributeError:
                print("Warning: Base file structure does not match expected format. Skipping base groups.")

    # 2. Load new alert rules from the directory
    print(f"Scanning {rules_dir} for new alert rules...")
    rule_files = glob.glob(os.path.join(rules_dir, "*.yaml")) + glob.glob(os.path.join(rules_dir, "*.yml"))
    
    for rule_file in rule_files:
        print(f"Processing {rule_file}...")
        with open(rule_file, 'r') as f:
            try:
                data = yaml.safe_load(f)
                if not data:
                    continue

                groups_to_add = []
                # Case A: Full structure
                if isinstance(data, dict) and 'grafana' in data:
                     groups_to_add = data.get('grafana', {}).get('alerting', {}).get('rules.yaml', {}).get('groups', [])
                
                # Case B: Dict with groups key
                elif isinstance(data, dict) and 'groups' in data:
                    groups_to_add = data['groups']

                # Case C: Just the groups list
                elif isinstance(data, list):
                    groups_to_add = data
                
                # Case D: Single group dict
                elif isinstance(data, dict) and 'name' in data and 'rules' in data:
                    groups_to_add = [data]
                
                if groups_to_add:
                    all_groups.extend(groups_to_add)
                    print(f"Found {len(groups_to_add)} groups in {rule_file}")
                else:
                    print(f"Warning: No valid alert groups found in {rule_file}")

            except Exception as e:
                print(f"Error processing {rule_file}: {e}")
                sys.exit(1)

    # 3. Merge groups by name
    merged_groups = {}
    
    for group in all_groups:
        name = group.get('name')
        if not name:
            continue
            
        if name not in merged_groups:
            merged_groups[name] = group
            # Initialize seen UIDs for this group
            merged_groups[name]['_seen_uids'] = set()
            if 'rules' in group:
                new_rules = []
                for rule in group['rules']:
                    uid = rule.get('uid')
                    if uid:
                        merged_groups[name]['_seen_uids'].add(uid)
                        new_rules.append(rule)
                    else:
                        new_rules.append(rule)
                merged_groups[name]['rules'] = new_rules
        else:
            # Merge rules into existing group
            existing_group = merged_groups[name]
            if 'rules' in group:
                for rule in group['rules']:
                    uid = rule.get('uid')
                    if uid:
                        if uid not in existing_group['_seen_uids']:
                            existing_group['_seen_uids'].add(uid)
                            existing_group['rules'].append(rule)
                        else:
                            print(f"Duplicate UID {uid} in group {name} skipped during merge.")
                    else:
                        existing_group['rules'].append(rule)

    # Convert merged groups back to list and remove temporary set
    final_group_list = []
    for name, group in merged_groups.items():
        if '_seen_uids' in group:
            del group['_seen_uids']
        final_group_list.append(group)

    # 4. Create Kubernetes ConfigMap structure with Logical Grouping
    
    # Determine domain from output filename or args
    domain = "wallet" if "wallet" in output_file else "pf"
    base_configmap_name = f"grafana-alert-rules-{domain}"

    # Group alerts by folder or name
    grouped_alerts = {}
    
    # List of generic folder names to ignore for grouping
    GENERIC_FOLDERS = ['loki alerts', 'general', 'other', 'alerts']

    for group in final_group_list:
        # STRIP relativeTimeRange removal block - we need this for Grafana 9.x+
        # if 'rules' in group:
        #     for rule in group['rules']:
        #         if 'data' in rule:
        #             for item in rule['data']:
        #                 if 'relativeTimeRange' in item:
        #                     del item['relativeTimeRange']

        # Determine the key for grouping
        folder = group.get('folder', '').strip()
        name = group.get('name', '').strip()
        
        key = 'general'
        
        # If folder is present and NOT generic, use it
        if folder and folder.lower() not in GENERIC_FOLDERS:
            key = folder
        # Otherwise, try to derive from name
        elif name:
            # Split by hyphen or space
            parts = re.split(r'[- ]+', name)
            if len(parts) >= 2:
                # Use first two parts as key (e.g. Wallet-Account -> wallet-account)
                key = f"{parts[0]}-{parts[1]}"
            else:
                # Use whole name if short
                key = name
        
        key = sanitize_name(key)
        
        # Ensure key is not empty
        if not key:
            key = 'general'
            
        if key not in grouped_alerts:
            grouped_alerts[key] = []
        grouped_alerts[key].append(group)

    import math

    print(f"Total groups: {len(final_group_list)}. Grouped into {len(grouped_alerts)} logical buckets.")

    all_configmaps = []
    generated_names = []
    
    # Max groups per ConfigMap chunk
    CHUNK_SIZE = 15

    for key, groups in grouped_alerts.items():
        # Calculate number of chunks needed for this logical group
        num_chunks = math.ceil(len(groups) / CHUNK_SIZE)
        
        for i in range(num_chunks):
            start_idx = i * CHUNK_SIZE
            end_idx = start_idx + CHUNK_SIZE
            chunk_groups = groups[start_idx:end_idx]
            
            # Ensure every group has a folder
            for g in chunk_groups:
                if 'folder' not in g or not g['folder']:
                    # Derive folder from group name or key
                    # e.g. key="wallet-account" -> folder="Wallet Account"
                    # or use the group name if available
                    if 'name' in g:
                         # Try to make it look nice: Wallet-Account-Group -> Wallet Account
                         derived_folder = g['name'].replace('-', ' ').replace('_', ' ')
                         # Remove "Group" suffix if present for cleaner folder names
                         derived_folder = re.sub(r'\s+Group$', '', derived_folder, flags=re.IGNORECASE).strip()
                         g['folder'] = derived_folder
                    else:
                        g['folder'] = key.replace('-', ' ').title()
            
            # ConfigMap name: grafana-alert-rules-wallet-{sanitized_folder_or_name}-{chunk_index}
            # Truncate key if it makes the name too long
            safe_key = key[:200]
            
            # If there's only 1 chunk, we don't strictly need the suffix, but adding it keeps things consistent and unique.
            # Let's add it always to avoid collision if we re-run with different chunk sizes.
            cm_name = f"{base_configmap_name}-{safe_key}-{i+1}"
            
            # Construct the alerts.yaml content for this chunk
            alerts_yaml_content = {
                'apiVersion': 1,
                'groups': chunk_groups
            }
            
            alerts_yaml_str = yaml.dump(alerts_yaml_content, default_flow_style=False, sort_keys=False)
            
            config_map = {
                'apiVersion': 'v1',
                'kind': 'ConfigMap',
                'metadata': {
                    'name': cm_name,
                    'namespace': 'observability',
                    'labels': {
                        'grafana_alert': '1'
                    }
                },
                'data': {
                    'alerts.yaml': alerts_yaml_str
                }
            }
            all_configmaps.append(config_map)
            generated_names.append(cm_name)

    # 5. Write all ConfigMaps to the single output file, separated by ---
    print(f"Writing {len(all_configmaps)} ConfigMaps to {output_file}...")
    with open(output_file, 'w') as f:
        yaml.dump_all(all_configmaps, f, default_flow_style=False, sort_keys=False)
    
    # 6. Write generated names to names_file if provided
    if names_file:
        print(f"Writing generated ConfigMap names to {names_file}...")
        with open(names_file, 'w') as f:
            for name in generated_names:
                f.write(f"{name}\n")

    print("Done.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python generate_alert_values.py <base_values_file> <rules_dir> <output_file> [names_file]")
        sys.exit(1)
    
    base_file = sys.argv[1]
    rules_directory = sys.argv[2]
    output_filename = sys.argv[3]
    names_filename = sys.argv[4] if len(sys.argv) > 4 else None
    
    merge_alerts(base_file, rules_directory, output_filename, names_filename)
