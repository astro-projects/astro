from __future__ import annotations

import argparse
from datetime import datetime
from time import sleep

import httpx

create_cluster_endpoint = "api/2.0/clusters/create"
get_cluster_endpoint = "api/2.0/clusters/get"
terminate_cluster_endpoint = "api/2.0/clusters/delete"


def build_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def create_cluster(host: str, headers: dict[str, str]) -> str:
    """Create databricks cluster and return cluster_id"""
    create_cluster_url = f"https://{host}/{create_cluster_endpoint}"
    json = {
        "cluster_name": "astro-sdk-testing",
        "spark_version": "12.2.x-scala2.12",
        "node_type_id": "i3.xlarge",
        "autoscale": {"min_workers": 1, "max_workers": 8},
        "runtime_engine": "PHOTON",
    }
    resp = httpx.post(create_cluster_url, json=json, headers=headers)
    return resp.json()["cluster_id"]


def wait_for_cluster(host: str, cluster_id: str, headers: dict[str, str]):
    get_cluster_url = f"https://{host}/{get_cluster_endpoint}"
    while True:
        resp = httpx.post(get_cluster_url, json={"cluster_id": cluster_id}, headers=headers)
        state = resp.json()["state"]
        print(datetime.now(), state)
        if state == "RUNNING":
            break
        sleep(1)


def terminate_cluster(host: str, cluster_id: str, headers: dict[str, str]):
    terminate_cluster_url = f"https://{host}/{terminate_cluster_endpoint}"
    httpx.post(terminate_cluster_url, json={"cluster_id": cluster_id}, headers=headers)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=["create_cluster", "wait_for_cluster", "terminate_cluster"])
    parser.add_argument("host")
    parser.add_argument("token")
    parser.add_argument("--cluster-id")
    args = parser.parse_args()

    operation = args.operation
    if operation == "create_cluster":
        databricks_cluster_id = create_cluster(args.host, build_headers(args.token))
        print(databricks_cluster_id)
    elif operation == "wait_for_cluster":
        wait_for_cluster(args.host, args.cluster_id, build_headers(args.token))
    elif operation == "terminate_cluster":
        terminate_cluster(args.host, args.cluster_id, build_headers(args.token))
