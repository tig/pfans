import yaml
from dotenv import load_dotenv
import os
import requests
import json

def create_or_update_ruleset():
    print("Starting script...")

    # Load environment variables
    load_dotenv()
    GRIPTAPE_API_KEY = os.getenv('GRIPTAPE_API_KEY')
    if not GRIPTAPE_API_KEY:
        raise ValueError("GRIPTAPE_API_KEY not found in environment variables")

    # Setup API headers
    headers = {
        'Authorization': f'Bearer {GRIPTAPE_API_KEY}',
        'Content-Type': 'application/json'
    }

    RULESET_ID = "bbec74c8-1b06-438f-a5d6-09c41a979aea"
    API_BASE = 'https://cloud.griptape.ai/api'

    try:
        # Load the rules from YAML
        print("Loading rules from YAML...")
        with open("porsche_expert_rules.yaml", "r") as f:
            rules_data = yaml.safe_load(f)
        print(f"Found {len(rules_data['rules'])} rules")

        # First create all rules
        print("\nCreating individual rules...")
        rule_ids = []
        for rule_data in rules_data["rules"]:
            rule_payload = {
                "name": rule_data["name"],
                "description": rule_data["description"],
                "rule": "\n".join(rule_data["patterns"]) if isinstance(rule_data["patterns"], list) else rule_data["patterns"]
            }
            
            rule_response = requests.post(
                f"{API_BASE}/rules",
                headers=headers,
                json=rule_payload
            )

            if rule_response.status_code in [200, 201]:
                rule_result = rule_response.json()
                rule_id = rule_result.get('rule_id')
                rule_ids.append(rule_id)
                print(f"Created rule '{rule_data['name']}' with ID: {rule_id}")
            else:
                print(f"Failed to create rule {rule_data['name']}. Status: {rule_response.status_code}")
                print(f"Response: {rule_response.text}")
                return False

        # Now create the ruleset with the rule IDs
        ruleset_data = {
            "name": rules_data["name"],
            "alias": "porsche_expert",
            "description": rules_data["description"],
            "rule_ids": rule_ids
        }

        # Check if ruleset exists
        if RULESET_ID != "update-later":
            print(f"\nChecking for existing ruleset {RULESET_ID}...")
            response = requests.get(f"{API_BASE}/rulesets/{RULESET_ID}", headers=headers)
            
            ruleset_exists = response.status_code == 200
            if ruleset_exists:
                print("Found existing ruleset, deleting...")
                delete_response = requests.delete(
                    f"{API_BASE}/rulesets/{RULESET_ID}",
                    headers=headers
                )
                if delete_response.status_code != 204:
                    print(f"Failed to delete existing ruleset. Status: {delete_response.status_code}")
                    print(f"Response: {delete_response.text}")
                    return False

        print("\nCreating ruleset with rules...")
        response = requests.post(
            f"{API_BASE}/rulesets",
            headers=headers,
            json=ruleset_data
        )

        if response.status_code not in [200, 201]:
            print(f"Failed to create ruleset. Status: {response.status_code}")
            print(f"Response: {response.text}")
            return False

        result = response.json()
        print(f"\nSuccessfully created ruleset")
        print(f"Ruleset ID: {result.get('ruleset_id')}")
        print(f"Access with alias: porsche_expert")
        
        print("\nFinal ruleset:")
        print(json.dumps(result, indent=2))

        return True

    except Exception as e:
        print(f"Error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    create_or_update_ruleset()