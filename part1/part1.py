import time
import google.auth
import googleapiclient.discovery
from googleapiclient.errors import HttpError

PROJECT = "erudite-course-507502-v9"
ZONE = "us-west1-a"
INSTANCE_NAME = "lab5-part1"

FIREWALL_NAME = "allow-5000"
NETWORK_TAG = "allow-5000"

MACHINE_TYPE = "e2-micro"

IMAGE_PROJECT = "ubuntu-os-cloud"
IMAGE_FAMILY = "ubuntu-2204-lts"

credentials, detected_project = google.auth.default()

compute = googleapiclient.discovery.build(
    "compute",
    "v1",
    credentials=credentials
)


def wait_for_zone_operation(compute, project, zone, operation):
    print(f"Waiting for operation {operation}...")

    while True:
        result = compute.zoneOperations().get(
            project=project,
            zone=zone,
            operation=operation
        ).execute()

        if result["status"] == "DONE":
            if "error" in result:
                raise Exception(result["error"])

            print("Operation completed.")
            return

        time.sleep(2)


def wait_for_global_operation(compute, project, operation):
    print(f"Waiting for operation {operation}...")

    while True:
        result = compute.globalOperations().get(
            project=project,
            operation=operation
        ).execute()

        if result["status"] == "DONE":
            if "error" in result:
                raise Exception(result["error"])

            print("Operation completed.")
            return

        time.sleep(2)


def create_firewall_rule():
    firewall = {
        "name": FIREWALL_NAME,
        "description": "Allow Flask traffic on TCP port 5000",
        "network": f"projects/{PROJECT}/global/networks/default",
        "direction": "INGRESS",
        "sourceRanges": ["0.0.0.0/0"],
        "targetTags": [NETWORK_TAG],
        "allowed": [
            {
                "IPProtocol": "tcp",
                "ports": ["5000"]
            }
        ]
    }

    try:
        print("Creating firewall rule allow-5000...")

        operation = compute.firewalls().insert(
            project=PROJECT,
            body=firewall
        ).execute()

        wait_for_global_operation(
            compute,
            PROJECT,
            operation["name"]
        )

        print("Firewall rule created.")

    except HttpError as error:
        if error.resp.status == 409:
            print("Firewall rule already exists.")
        else:
            raise


STARTUP_SCRIPT = """#!/bin/bash
apt-get update
apt-get install -y python3-pip
pip3 install flask

cat > /opt/app.py <<'EOF'
from flask import Flask

app = Flask(__name__)

@app.route("/")
def home():
    return "Hello from Lab 5 - Programmable Cloud!"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
EOF

nohup python3 /opt/app.py > /var/log/flask-app.log 2>&1 &
"""


def instance_exists():
    try:
        compute.instances().get(
            project=PROJECT,
            zone=ZONE,
            instance=INSTANCE_NAME
        ).execute()

        return True

    except HttpError as error:
        if error.resp.status == 404:
            return False

        raise


def create_instance():
    print("Getting Ubuntu image...")

    image = compute.images().getFromFamily(
        project=IMAGE_PROJECT,
        family=IMAGE_FAMILY
    ).execute()

    config = {
        "name": INSTANCE_NAME,

        "machineType": (
            f"zones/{ZONE}/machineTypes/{MACHINE_TYPE}"
        ),

        "tags": {
            "items": [NETWORK_TAG]
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
                    f"projects/{PROJECT}/global/networks/default"
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
                    "value": STARTUP_SCRIPT
                }
            ]
        }
    }

    print(f"Creating VM {INSTANCE_NAME}...")

    return compute.instances().insert(
        project=PROJECT,
        zone=ZONE,
        body=config
    ).execute()


def get_external_ip():
    instance = compute.instances().get(
        project=PROJECT,
        zone=ZONE,
        instance=INSTANCE_NAME
    ).execute()

    return (
        instance["networkInterfaces"][0]
        ["accessConfigs"][0]
        ["natIP"]
    )


def main():
    print("-------------------------------------")
    print("Lab 5 - Part 1")
    print("-------------------------------------")
    print(f"Project: {PROJECT}")
    print(f"Zone: {ZONE}")
    print()

    create_firewall_rule()

    print()
    print("Checking VM...")

    if instance_exists():
        print(f"VM {INSTANCE_NAME} already exists.")
    else:
        operation = create_instance()

        wait_for_zone_operation(
            compute,
            PROJECT,
            ZONE,
            operation["name"]
        )

    external_ip = get_external_ip()

    print()
    print("-------------------------------------")
    print("VM successfully provisioned!")
    print("-------------------------------------")
    print(f"Instance: {INSTANCE_NAME}")
    print(f"External IP: {external_ip}")
    print(f"Flask URL: http://{external_ip}:5000")
    print()
    print("The startup script may take a minute to finish.")


if __name__ == "__main__":
    main()
