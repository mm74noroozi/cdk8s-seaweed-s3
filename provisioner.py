from unittest import result
from fastapi import FastAPI
from minio import Minio
from kubernetes import client, config, utils
from main import MyChart
import uvicorn
from cdk8s import App

app = FastAPI()

config.load_kube_config()
v1 = client.CoreV1Api()

@app.get(path="/health")
def health_probe() -> dict[str, str]:
    return {"health": "ok"}

@app.get("/storage", description="list storages")
def list():
    list_ = v1.list_namespace()
    return [{"id": ns.metadata.uid,
             "name": ns.metadata.name} for ns in list_.items \
                if "type" in ns.metadata.labels and ns.metadata.labels["type"] == "storage"]

@app.get("/storage/{id}", description="list storages")
def detail(id: str):
    ns = v1.read_namespace(id)
    if not ns:
        return {"status": "not found"}
    name = ns.metadata.name
    return name

@app.post("/storage", description="create a storage")
def create_storage(name: str, replication: int = 1) -> dict[str, str]:
    if replication < 1:
        # TODO change status code
        return {"status": "replication must be greater than 0"}
    if replication > 9:
        return {"status": "replication must be less than 9"}
    # if name in [ns.metadata.name for ns in v1.list_namespace().items]:
    #     return {"status": "name already exists"}
    app = App()
    MyChart(app, name, replication)
    app.synth()
    api = client.ApiClient()
    utils.create_from_yaml(api, yaml_file=f"dist/{name}.k8s.yaml")
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app)