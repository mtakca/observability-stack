import yaml
import os
import sys
import glob
import subprocess

def get_alert_uids(rules_dir):
    """
    Scans the given directory for YAML files and extracts alert rule UIDs.
    """
    uids = []
    # Support both .yaml and .yml extensions
    rule_files = glob.glob(os.path.join(rules_dir, "*.yaml")) + glob.glob(os.path.join(rules_dir, "*.yml"))
    
    print(f"Scanning {len(rule_files)} files in {rules_dir}...")

    for rule_file in rule_files:
        with open(rule_file, 'r') as f:
            try:
                data = yaml.safe_load(f)
                if not data:
                    continue
                
                groups = []
                # Handle different YAML structures
                if isinstance(data, dict):
                    if 'grafana' in data:
                        groups = data.get('grafana', {}).get('alerting', {}).get('rules.yaml', {}).get('groups', [])
                    elif 'groups' in data:
                        groups = data['groups']
                    elif 'name' in data and 'rules' in data:
                        groups = [data]
                elif isinstance(data, list):
                    groups = data

                for group in groups:
                    if 'rules' in group:
                        for rule in group['rules']:
                            uid = rule.get('uid')
                            if uid:
                                uids.append(uid)
            except Exception as e:
                print(f"Error processing {rule_file}: {e}")
    
    return uids

def execute_deletion_in_pod(uids, namespace, pod_label="app.kubernetes.io/name=grafana"):
    """
    Executes curl DELETE commands inside the Grafana pod.
    """
    if not uids:
        print("No UIDs found to delete.")
        return

    # 1. Find the pod name
    try:
        cmd_get_pod = [
            "kubectl", "get", "pods", "-n", namespace, "-l", pod_label, 
            "-o", "jsonpath={.items[0].metadata.name}"
        ]
        pod_name = subprocess.check_output(cmd_get_pod).decode('utf-8').strip()
        print(f"Targeting pod: {pod_name}")
    except subprocess.CalledProcessError as e:
        print(f"Error finding pod with label {pod_label}: {e}")
        sys.exit(1)
    except IndexError:
        print(f"No pod found with label {pod_label} in namespace {namespace}")
        sys.exit(1)

    # 2. Construct the shell script to run inside the pod
    # We use a shell loop or multiple commands.
    # Using env vars for credentials if available, defaulting to admin:admin
    
    # We will construct a single shell command that iterates or runs multiple curls.
    # To avoid command length limits, we can feed it via stdin to /bin/sh
    
    commands = []
    commands.append("echo 'Starting deletion process...'")
    
    # Define base URL and Auth
    # We use single quotes for the script content to avoid shell expansion by the local shell
    # But we need to be careful with inner quotes.
    
    # Better approach: Create a temporary script content
    script_content = [
        "#!/bin/sh",
        "USER=${GF_SECURITY_ADMIN_USER:-admin}",
        "PASS=${GF_SECURITY_ADMIN_PASSWORD:-admin}",
        "URL='http://localhost:3000/api/v1/provisioning/alert-rules'",
        ""
    ]
    
    for uid in uids:
        # curl -X DELETE -u user:pass url/uid
        # We use -s for silent, -o /dev/null to hide output, -w to show status code
        cmd = f"echo 'Deleting rule {uid}...' && curl -X DELETE -s -u \"$USER:$PASS\" \"$URL/{uid}\""
        script_content.append(cmd)
        
    full_script = "\n".join(script_content)
    
    print(f"Prepared deletion script for {len(uids)} rules.")

    # 3. Execute via kubectl exec
    try:
        kubectl_cmd = ["kubectl", "exec", "-i", pod_name, "-n", namespace, "--", "/bin/sh"]
        
        process = subprocess.Popen(kubectl_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate(input=full_script.encode('utf-8'))
        
        if process.returncode != 0:
            print(f"Error executing deletion script: {stderr.decode('utf-8')}")
            sys.exit(1)
            
        print("Deletion Output:")
        print(stdout.decode('utf-8'))
        
    except Exception as e:
        print(f"Failed to execute kubectl command: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python delete_alert_rules.py <rules_dir> <namespace> [pod_label]")
        sys.exit(1)
    
    rules_dir = sys.argv[1]
    namespace = sys.argv[2]
    pod_label = sys.argv[3] if len(sys.argv) > 3 else "app.kubernetes.io/name=grafana"
    
    print(f"Starting API-based alert rule deletion for {rules_dir} in {namespace}...")
    
    uids = get_alert_uids(rules_dir)
    print(f"Found {len(uids)} alert UIDs.")
    
    if uids:
        execute_deletion_in_pod(uids, namespace, pod_label)
    else:
        print("No alert rules found to delete.")
