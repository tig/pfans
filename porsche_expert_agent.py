from griptape.structures import Agent
from griptape.rules import Rule, Ruleset
from griptape.tools import FileManagerTool
import yaml
import json

# Load the rules
with open("porsche_expert_rules.yaml", "r") as f:
    rules_data = yaml.safe_load(f)

# Create ruleset
rules = [
    Rule(
        rule_data["description"],  # Description is the main content
        meta={                     # Meta contains additional info
            "name": rule_data["name"],
            "patterns": rule_data["patterns"]
        }
    )
    for rule_data in rules_data["rules"]
]

porsche_ruleset = Ruleset(
    rules_data["name"],           # Name as first argument
    rules=rules,                  # Rules as keyword argument
    meta={                        # Meta contains additional info
        "description": rules_data["description"]
    }
)

# Create tools
file_tool = FileManagerTool(off_prompt=True)  # Keep large files off prompt by default

# Create the agent with our ruleset and tools
agent = Agent(
    rules=porsche_ruleset,
    tools=[file_tool]
)

def load_archive():
    """Load the mailing list archive into the agent's context"""
    with open("output/mailing_list_archive.json", "r", encoding='utf-8') as f:
        return json.load(f)

# Example usage
if __name__ == "__main__":
    from griptape.utils import Chat
    
    print(f"Initializing Porsche Expert Agent with {len(rules)} rules")
    print("Loading mailing list archive...")
    
    # Start interactive chat
    Chat(agent).start()