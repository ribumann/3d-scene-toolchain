#!/usr/bin/env python3
"""Explicit-target Azure preflight/provision/cleanup. Never reads other projects' secrets."""

import argparse
import ipaddress
import json
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKU = "Standard_NC4as_T4_v3"


def az(arguments):
    completed = subprocess.run(
        ["az", *arguments, "--only-show-errors", "--output", "json"],
        text=True, capture_output=True,
    )
    if completed.returncode:
        # Azure diagnostics may include subscription/tenant IDs. Keep this CLI
        # focused on local execution; workflows mask those identities first.
        raise RuntimeError(completed.stderr.strip() or "Azure CLI command failed")
    return json.loads(completed.stdout) if completed.stdout.strip() else None


def validate_identity(subscription, tenant):
    pattern = r"^[0-9a-fA-F-]{36}$"
    if not re.fullmatch(pattern, subscription) or not re.fullmatch(pattern, tenant):
        raise ValueError("Provide exact subscription and tenant UUIDs through your configured environment")
    account = az(["account", "show", "--subscription", subscription])
    if account["id"].lower() != subscription.lower() or account["tenantId"].lower() != tenant.lower():
        raise ValueError("Active subscription/tenant does not match the explicitly approved target")
    if account["state"] != "Enabled":
        raise ValueError("Target subscription is not enabled")
    return account


def inspect(subscription, tenant):
    validate_identity(subscription, tenant)
    skus = az(["vm", "list-skus", "--subscription", subscription, "--location", "italynorth", "--size", SKU, "--all"])
    candidates = [sku for sku in skus if sku["name"] == SKU and sku["resourceType"] == "virtualMachines"]
    if not candidates or any(candidate.get("restrictions") for candidate in candidates):
        raise ValueError("Italy North T4 SKU is absent or restricted for this subscription. No VM was deployed.")
    usages = az(["vm", "list-usage", "--subscription", subscription, "--location", "italynorth"])
    family = next((usage for usage in usages if usage["name"]["value"].lower() == "standardncast4_v3family"), None)
    total = next((usage for usage in usages if usage["name"]["value"].lower() == "cores"), None)
    if not family or family["limit"] - family["currentValue"] < 4:
        raise ValueError("Fewer than four available NCasT4_v3 family vCPUs. Request quota before deployment.")
    if not total or total["limit"] - total["currentValue"] < 4:
        raise ValueError("Fewer than four regional vCPUs remain available")
    return {
        "target_verified": True, "region": "italynorth", "sku": SKU,
        "family_available_vcpus": family["limit"] - family["currentValue"],
        "regional_available_vcpus": total["limit"] - total["currentValue"],
        "capacity_warning": "Quota/SKU availability does not guarantee current VM allocation capacity.",
    }


def validate_creation(name, cidr, key, hours):
    if not re.fullmatch(r"scene-twin-[a-z0-9-]{3,18}", name):
        raise ValueError("Resource group must be a dedicated scene-twin-<unique-name> group")
    network = ipaddress.ip_network(cidr, strict=True)
    if network.version != 4 or network.prefixlen != 32 or not network.network_address.is_global:
        raise ValueError("SSH must be restricted to a public operator IPv4 /32")
    text = key.read_text().strip()
    if not text.startswith(("ssh-ed25519 ", "ssh-rsa ")):
        raise ValueError("Expected an OpenSSH public key, not private key material")
    if not 1 <= hours <= 8:
        raise ValueError("Use a bounded duration of 1..8 hours")
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight", "create", "delete"))
    parser.add_argument("--subscription", required=True)
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--group")
    parser.add_argument("--ssh-source-cidr")
    parser.add_argument("--ssh-public-key", type=Path)
    parser.add_argument("--hours", type=int, default=2)
    parser.add_argument("--confirm-paid-create", action="store_true")
    parser.add_argument("--confirm-delete", action="store_true")
    args = parser.parse_args()
    if not shutil.which("az"):
        parser.error("Azure CLI is unavailable. Authenticate with az login --tenant <approved-tenant> on the authorized operator host.")
    if args.command == "preflight":
        print(json.dumps(inspect(args.subscription, args.tenant), indent=2))
        return
    if args.command == "create":
        if not args.confirm_paid_create or not args.group or not args.ssh_source_cidr or not args.ssh_public_key:
            parser.error("Creation requires an explicit paid-create flag, dedicated group, restricted SSH CIDR and public key")
        key = validate_creation(args.group, args.ssh_source_cidr, args.ssh_public_key, args.hours)
        inspect(args.subscription, args.tenant)
        if az(["group", "exists", "--subscription", args.subscription, "--name", args.group]):
            raise ValueError("Dedicated group already exists; refusing to mutate or reuse it")
        deadline = datetime.now(timezone.utc) + timedelta(hours=args.hours)
        tags = ["project=3d-scene-toolchain", "managedBy=scene-toolchain", f"expiresAt={deadline.isoformat()}"]
        az(["group", "create", "--subscription", args.subscription, "--name", args.group, "--location", "italynorth", "--tags", *tags])
        try:
            result = az([
                "deployment", "group", "create", "--subscription", args.subscription,
                "--resource-group", args.group, "--name", "scene-worker",
                "--template-file", str(ROOT / "infra/azure/gpu.bicep"),
                "--parameters", f"name={args.group}", f"sshPublicKey={key}",
                f"sshSourceCidr={args.ssh_source_cidr}", f"shutdownTimeUtc={deadline:%H%M}",
                f"expiresAt={deadline.isoformat()}",
            ])
        except Exception:
            # Do not destroy an ambiguous pre-existing group: this branch is only
            # reachable after we successfully created a brand-new dedicated group.
            az(["group", "delete", "--subscription", args.subscription, "--name", args.group, "--yes"])
            raise
        print(json.dumps({
            "group": args.group, "outputs": result["properties"]["outputs"],
            "auto_shutdown_utc": f"{deadline:%H:%M}",
            "required_cleanup": "Run delete after retrieval; deallocation does not remove disks or IP charges.",
        }, indent=2))
    else:
        validate_identity(args.subscription, args.tenant)
        if not args.confirm_delete or not args.group or not re.fullmatch(r"scene-twin-[a-z0-9-]{3,18}", args.group):
            parser.error("Deletion requires a dedicated group name and --confirm-delete")
        group = az(["group", "show", "--subscription", args.subscription, "--name", args.group])
        if group.get("tags", {}).get("managedBy") != "scene-toolchain" or group.get("tags", {}).get("project") != "3d-scene-toolchain":
            raise ValueError("Refusing deletion: resource group ownership tags do not match")
        az(["group", "delete", "--subscription", args.subscription, "--name", args.group, "--yes"])
        print(json.dumps({"deleted_group": args.group}))


if __name__ == "__main__":
    main()
