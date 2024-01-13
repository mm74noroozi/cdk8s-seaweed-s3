from unittest import result
from fastapi import FastAPI
from minio import Minio
from kubernetes import client, config, utils
from main import MyChart
import uvicorn
from cdk8s import App
import os

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
    ns_map ={ns.metadata.uid: ns.metadata.name for ns in v1.list_namespace() if "type" in ns.metadata.labels and ns.metadata.labels["type"] == "storage"} 
    if id not in ns_map:
        return {"status": "not found"}
    name = ns_map[id]
    s3 = Minio(endpoint=f"filer-service.{name}.svc.cluster.local:8333", 
               access_key="blahblah...", secret_key="blahblah...",
               secure=False)
    res={}
    res['name'] = name
    res['buckets'] = []
    for bucket in s3.list_buckets():
        objects_number: int = len(list(s3.list_objects(bucket.name)))
        res.append({"name": bucket.name, "num_objects": objects_number})
    return res

@app.post("/storage", description="create a storage")
def create_storage(name: str, replication: int = 1) -> dict[str, str]:
    if replication < 1:
        # TODO change status code
        return {"status": "replication must be greater than 0"}
    if replication > 9:
        return {"status": "replication must be less than 9"}
    if name in [ns.metadata.name for ns in v1.list_namespace().items]:
        return {"status": "name already exists"}
    app = App()
    MyChart(app, name, replication)
    app.synth()
    os.system(f"kubectl apply dist/{name}.k8s.yaml")
    return {"status": "ok"}

@app.delete("/storage", description="delete a storage")
def create_storage(id) -> dict[str, str]:
    ns_map ={ns.metadata.uid: ns.metadata.name for ns in v1.list_namespace() if "type" in ns.metadata.labels and ns.metadata.labels["type"] == "storage"} 
    if id not in ns_map:
        return {"status": "not found"}
    name = ns_map[id]
    app = App()
    MyChart(scope=app, ns=name, replica_count=1)
    app.synth()
    api = client.ApiClient()
    os.system(f'kubectl delete -f dist/{name}.k8s.yaml')
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run(app)