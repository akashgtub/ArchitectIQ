"""
Validates YAML syntax across all Ansible playbooks, roles, and configuration files.
"""
import glob
import sys
import yaml

def main():
    patterns = [
        "infrastructure/ansible/**/*.yml",
        "infrastructure/ansible/**/*.yaml",
    ]
    files = []
    for pattern in patterns:
        files.extend(glob.glob(pattern, recursive=True))

    errors = 0
    for f in sorted(files):
        try:
            with open(f, "r", encoding="utf-8") as fp:
                yaml.safe_load(fp)
            print(f"  PASS: {f}")
        except Exception as e:
            print(f"  FAIL: {f} -> {e}")
            errors += 1

    print(f"\nValidated {len(files)} Ansible YAML files with {errors} errors.")
    return errors

if __name__ == "__main__":
    sys.exit(main())

