import time
import google.auth
import googleapiclient.discovery
from googleapiclient.errors import HttpError


PROJECT = "erudite-course-507502-v9"
ZONE = "us-west1-a"

SOURCE_INSTANCE = "lab5-part1"
SNAPSHOT_NAME = f"base-snapshot-{SOURCE_INSTANCE}"

MACHINE_TYPE = "e2-micro"
NETWORK_TAG = "allow-5000"

NEW_INSTANCES = [
    "lab5-part2-1",
    "lab5-part2-2",
    "lab5-part2-3"
]


credentials, _ = google.auth.default()

compute = googleapiclient.discovery.build(
    "compute",
    "v1",
    credentials=credentials
)


def wait_for_zone_operation(operation_name):
    while True:
        result = compute.zoneOperations().get(
            project=PROJECT,
            zone=ZONE,
            operation=operation_name
        ).execute()

        if result["status"] == "DONE":
            if "error" in result:
                raise Exception(result["error"])

            return

        time.sleep(2)


def wait_for_global_operation(operation_name):
    while True:
        result = compute.globalOperations().get(
            project=PROJECT,
            operation=operation_name
        ).execute()

        if result["status"] == "DONE":
            if "error" in result:
                raise Exception(result["error"])

            return

        time.sleep(2)


def get_boot_disk_name():
    print(f"Finding boot disk for {SOURCE_INSTANCE}...")

    instance = compute.instances().get(
        project=PROJECT,
        zone=ZONE,
        instance=SOURCE_INSTANCE
    ).execute()

    for disk in instance["disks"]:
        if disk.get("boot"):
            disk_name = disk["source"].split("/")[-1]

            print(f"Boot disk: {disk_name}")
            return disk_name

    raise Exception("Could not find boot disk.")


def snapshot_exists():
    try:
        compute.snapshots().get(
            project=PROJECT,
            snapshot=SNAPSHOT_NAME
        ).execute()

        return True

    except HttpError as error:
        if error.resp.status == 404:
            return False

        raise


def create_snapshot(disk_name):
    if snapshot_exists():
        print(f"Snapshot {SNAPSHOT_NAME} already exists.")
        return

    print()
    print(f"Creating snapshot {SNAPSHOT_NAME}...")

    body = {
        "name": SNAPSHOT_NAME,
        "description": (
            f"Snapshot created from {SOURCE_INSTANCE} "
            "for Lab 5 Part 2"
        )
    }

    operation = compute.disks().createSnapshot(
        project=PROJECT,
        zone=ZONE,
        disk=disk_name,
        body=body
    ).execute()

    print("Waiting for snapshot operation...")

    wait_for_zone_operation(
        operation["name"]
    )

    print("Snapshot created successfully.")


def instance_exists(instance_name):
    try:
        compute.instances().get(
            project=PROJECT,
            zone=ZONE,
            instance=instance_name
        ).execute()

        return True

    except HttpError as error:
        if error.resp.status == 404:
            return False

        raise


def create_instance_from_snapshot(instance_name):
    snapshot_url = (
        f"projects/{PROJECT}/global/snapshots/{SNAPSHOT_NAME}"
    )

    config = {
        "name": instance_name,

        "machineType": (
            f"zones/{ZONE}/machineTypes/{MACHINE_TYPE}"
        ),

        "tags": {
            "items": [
                NETWORK_TAG
            ]
        },

        "disks": [
            {
                "boot": True,
                "autoDelete": True,

                "initializeParams": {
                    "sourceSnapshot": snapshot_url
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

        # Flask is already installed in the snapshot.
        # This simply starts the existing app on boot.
        "metadata": {
            "items": [
                {
                    "key": "startup-script",
                    "value": """#!/bin/bash
nohup python3 /opt/app.py > /var/log/flask-app.log 2>&1 &
"""
                }
            ]
        }
    }

    print()
    print(f"Creating {instance_name}...")

    start_time = time.perf_counter()

    operation = compute.instances().insert(
        project=PROJECT,
        zone=ZONE,
        body=config
    ).execute()

    wait_for_zone_operation(
        operation["name"]
    )

    end_time = time.perf_counter()

    elapsed_time = end_time - start_time

    print(
        f"{instance_name} created in "
        f"{elapsed_time:.2f} seconds."
    )

    return elapsed_time


def write_timing_file(timings):
    with open("TIMING.md", "w") as file:
        file.write("# Lab 5 Part 2 Timing Results\n\n")

        file.write(
            f"Source snapshot: `{SNAPSHOT_NAME}`\n\n"
        )

        file.write(
            f"Zone: `{ZONE}`\n\n"
        )

        file.write(
            "| Instance | Provisioning Time (seconds) |\n"
        )

        file.write(
            "|---|---:|\n"
        )

        for name, elapsed in timings:
            file.write(
                f"| {name} | {elapsed:.2f} |\n"
            )

    print()
    print("TIMING.md created.")


def main():
    print("-------------------------------------")
    print("Lab 5 - Part 2")
    print("-------------------------------------")

    print(f"Project: {PROJECT}")
    print(f"Zone: {ZONE}")
    print(f"Source instance: {SOURCE_INSTANCE}")
    print()

    disk_name = get_boot_disk_name()

    create_snapshot(
        disk_name
    )

    timings = []

    print()
    print("-------------------------------------")
    print("Creating three instances")
    print("-------------------------------------")

    for instance_name in NEW_INSTANCES:

        if instance_exists(instance_name):
            print(
                f"{instance_name} already exists."
            )

            timings.append(
                (instance_name, 0.0)
            )

        else:
            elapsed = create_instance_from_snapshot(
                instance_name
            )

            timings.append(
                (instance_name, elapsed)
            )

    write_timing_file(
        timings
    )

    print()
    print("-------------------------------------")
    print("Part 2 complete")
    print("-------------------------------------")

    for name, elapsed in timings:
        print(
            f"{name}: {elapsed:.2f} seconds"
        )


if __name__ == "__main__":
    main()
