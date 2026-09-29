import time
import google.auth
import googleapiclient.discovery
from googleapiclient.errors import HttpError


PROJECT = "erudite-course-507502-v9"
ZONE = "us-west1-a"

VM1_NAME = "lab5-part3-vm1"
VM2_NAME = "lab5-part3-vm2"

MACHINE_TYPE = "e2-micro"

SERVICE_ACCOUNT_EMAIL = (
    "lab5-vm-launcher@"
    "erudite-course-507502-v9.iam.gserviceaccount.com"
)


credentials, _ = google.auth.default()

compute = googleapiclient.discovery.build(
    "compute",
    "v1",
    credentials=credentials
)


def wait_for_zone_operation(operation_name):
    print(f"Waiting for operation {operation_name}...")

    while True:
        result = compute.zoneOperations().get(
            project=PROJECT,
            zone=ZONE,
            operation=operation_name
        ).execute()

        if result["status"] == "DONE":
            if "error" in result:
                raise Exception(result["error"])

            print("Operation completed.")
            return

        time.sleep(2)


def instance_exists(name):
    try:
        compute.instances().get(
            project=PROJECT,
            zone=ZONE,
            instance=name
        ).execute()

        return True

    except HttpError as error:
        if error.resp.status == 404:
            return False
        raise


VM2_STARTUP_SCRIPT = """#!/bin/bash

apt-get update
apt-get install -y python3-pip
pip3 install flask

cat > /opt/app.py <<'EOF'
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "Hello from Lab 5 Part 3 - VM2!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
EOF

nohup python3 /opt/app.py > /var/log/flask-app.log 2>&1 &
"""


VM1_LAUNCH_VM2_CODE = r'''
import time
import urllib.request

import google.auth
import googleapiclient.discovery
from googleapiclient.errors import HttpError


METADATA_BASE = (
    "http://metadata.google.internal/"
    "computeMetadata/v1/"
)


def get_metadata(path):
    request = urllib.request.Request(
        METADATA_BASE + path,
        headers={"Metadata-Flavor": "Google"}
    )

    with urllib.request.urlopen(request) as response:
        return response.read().decode("utf-8")


project = get_metadata("project/project-id").strip()
zone = get_metadata(
    "instance/attributes/zone"
).strip()
vm2_name = get_metadata(
    "instance/attributes/vm2-name"
).strip()


credentials, _ = google.auth.default()

compute = googleapiclient.discovery.build(
    "compute",
    "v1",
    credentials=credentials
)


def wait_for_operation(operation_name):
    while True:
        result = compute.zoneOperations().get(
            project=project,
            zone=zone,
            operation=operation_name
        ).execute()

        if result["status"] == "DONE":
            if "error" in result:
                raise Exception(result["error"])
            return

        time.sleep(2)


def vm_exists():
    try:
        compute.instances().get(
            project=project,
            zone=zone,
            instance=vm2_name
        ).execute()

        return True

    except HttpError as error:
        if error.resp.status == 404:
            return False
        raise


if vm_exists():
    print(
        f"VM2 {vm2_name} already exists."
    )

else:
    print("Getting Ubuntu image...")

    image = compute.images().getFromFamily(
        project="ubuntu-os-cloud",
        family="ubuntu-2204-lts"
    ).execute()

    with open(
        "/srv/vm2-startup-script.sh",
        "r"
    ) as file:
        vm2_startup_script = file.read()

    config = {
        "name": vm2_name,

        "machineType": (
            f"zones/{zone}/machineTypes/e2-micro"
        ),

        "tags": {
            "items": [
                "allow-5000"
            ]
        },

        "disks": [
            {
                "boot": True,
                "autoDelete": True,

                "initializeParams": {
                    "sourceImage": image["selfLink"]
                }
            }
        ],

        "networkInterfaces": [
            {
                "network": (
                    f"projects/{project}/"
                    "global/networks/default"
                ),

                "accessConfigs": [
                    {
                        "name": "External NAT",
                        "type": "ONE_TO_ONE_NAT"
                    }
                ]
            }
        ],

        "metadata": {
            "items": [
                {
                    "key": "startup-script",
                    "value": vm2_startup_script
                }
            ]
        }
    }

    print(
        f"VM1 is creating VM2: {vm2_name}"
    )

    operation = compute.instances().insert(
        project=project,
        zone=zone,
        body=config
    ).execute()

    wait_for_operation(
        operation["name"]
    )

    print("VM2 creation completed.")


instance = compute.instances().get(
    project=project,
    zone=zone,
    instance=vm2_name
).execute()

external_ip = (
    instance["networkInterfaces"][0]
    ["accessConfigs"][0]
    ["natIP"]
)

print(
    f"VM2 external IP: {external_ip}"
)

print(
    f"VM2 Flask URL: "
    f"http://{external_ip}:5000"
)
'''


VM1_STARTUP_SCRIPT = """#!/bin/bash

mkdir -p /srv
cd /srv

curl -fsS \
  -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/attributes/vm1-launch-vm2-code \
  -o /srv/vm1-launch-vm2-code.py

curl -fsS \
  -H "Metadata-Flavor: Google" \
  http://metadata.google.internal/computeMetadata/v1/instance/attributes/vm2-startup-script \
  -o /srv/vm2-startup-script.sh

apt-get update
apt-get install -y python3-pip

pip3 install --upgrade \
  google-api-python-client \
  google-auth \
  google-auth-httplib2

python3 /srv/vm1-launch-vm2-code.py \
  > /var/log/vm1-launch-vm2.log 2>&1
"""


def create_vm1():
    print("Finding Ubuntu image...")

    image = compute.images().getFromFamily(
        project="ubuntu-os-cloud",
        family="ubuntu-2204-lts"
    ).execute()

    config = {
        "name": VM1_NAME,

        "machineType": (
            f"zones/{ZONE}/machineTypes/"
            f"{MACHINE_TYPE}"
        ),

        "disks": [
            {
                "boot": True,
                "autoDelete": True,

                "initializeParams": {
                    "sourceImage": image["selfLink"]
                }
            }
        ],

        "networkInterfaces": [
            {
                "network": (
                    f"projects/{PROJECT}/"
                    "global/networks/default"
                ),

                "accessConfigs": [
                    {
                        "name": "External NAT",
                        "type": "ONE_TO_ONE_NAT"
                    }
                ]
            }
        ],

        "serviceAccounts": [
            {
                "email": SERVICE_ACCOUNT_EMAIL,

                "scopes": [
                    "https://www.googleapis.com/"
                    "auth/cloud-platform"
                ]
            }
        ],

        "metadata": {
            "items": [
                {
                    "key": "startup-script",
                    "value": VM1_STARTUP_SCRIPT
                },

                {
                    "key": "vm1-launch-vm2-code",
                    "value": VM1_LAUNCH_VM2_CODE
                },

                {
                    "key": "vm2-startup-script",
                    "value": VM2_STARTUP_SCRIPT
                },

                {
                    "key": "zone",
                    "value": ZONE
                },

                {
                    "key": "vm2-name",
                    "value": VM2_NAME
                }
            ]
        }
    }

    print(
        f"Creating VM1: {VM1_NAME}"
    )

    operation = compute.instances().insert(
        project=PROJECT,
        zone=ZONE,
        body=config
    ).execute()

    wait_for_zone_operation(
        operation["name"]
    )


def main():
    print("-------------------------------------")
    print("Lab 5 - Part 3")
    print("-------------------------------------")

    print(f"Project: {PROJECT}")
    print(f"Zone: {ZONE}")
    print(f"VM1: {VM1_NAME}")
    print(f"VM2: {VM2_NAME}")
    print()

    if instance_exists(VM1_NAME):
        print(
            f"{VM1_NAME} already exists."
        )
    else:
        create_vm1()

    vm1 = compute.instances().get(
        project=PROJECT,
        zone=ZONE,
        instance=VM1_NAME
    ).execute()

    vm1_ip = (
        vm1["networkInterfaces"][0]
        ["accessConfigs"][0]
        ["natIP"]
    )

    print()
    print("-------------------------------------")
    print("VM1 successfully provisioned")
    print("-------------------------------------")
    print(f"VM1 external IP: {vm1_ip}")
    print()
    print(
        "VM1 startup script will now "
        "create VM2."
    )

    print(
        "Check /var/log/vm1-launch-vm2.log "
        "on VM1 for progress."
    )


if __name__ == "__main__":
    main()
