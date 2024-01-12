#!/usr/bin/env python
from typing import Any
from constructs import Construct
from cdk8s import App, Chart
import toml 
from imports import k8s
import base64

class MyChart(Chart):
   def __init__(self, scope: Construct, ns: str, replica_count: int):
        super().__init__(scope, ns)
        k8s.KubeNamespace(self, "ns", metadata=k8s.ObjectMeta(name=ns, labels={'type': 'storage'}))
        k8s.KubeDeployment(self, "filerdb",
                           metadata=k8s.ObjectMeta(name="filerdb-deployment", namespace=ns),
                           spec=k8s.DeploymentSpec(
                                replicas=1,
                                selector=k8s.LabelSelector(match_labels={"app": "filerdb"}),
                                template=k8s.PodTemplateSpec(
                                    metadata=k8s.ObjectMeta(labels={"app": "filerdb"}),
                                    spec=k8s.PodSpec(containers=[
                                        k8s.Container(
                                            name="postgres",
                                            image="hub.hamdocker.ir/library/postgres:16", 
                                            ports=[k8s.ContainerPort(container_port=5432)],
                                            env=[
                                                k8s.EnvVar(name="POSTGRES_USER", value="weed"),
                                                k8s.EnvVar(name="POSTGRES_PASSWORD", value="No1QLNwxB08q"),
                                                k8s.EnvVar(name="POSTGRES_DB", value="filerdb"),
                                            ]
                                        )
                                ])
                           )
                       )
                   )
        k8s.KubeService(self, "filerdb-service",
                        metadata=k8s.ObjectMeta(name="filerdb-service", namespace=ns),
                        spec=k8s.ServiceSpec(
                            ports=[k8s.ServicePort(port=5432)],
                            selector={"app": "filerdb"}
                        )
                    )
        with open("filer.toml", "r") as f:
            config: dict[str, Any] = toml.load(f)
            config["hostname"] = f"filerdb-service.{ns}.svc.cluster.local"
        k8s.KubeConfigMap(self, "filer-config", 
                          metadata=k8s.ObjectMeta(name="filer-config", namespace=ns),
                          data={"filer.toml": toml.dumps(config)})
        k8s.KubeDeployment(self, "filer",
                           metadata=k8s.ObjectMeta(name="filer-deployment", namespace=ns),
                       spec=k8s.DeploymentSpec(
                           replicas=1,
                           selector=k8s.LabelSelector(match_labels={"app": "filer"}),
                           template=k8s.PodTemplateSpec(
                               metadata=k8s.ObjectMeta(labels={"app": "filer"}),
                               spec=k8s.PodSpec(containers=[
                                   k8s.Container(
                                       name="filer",
                                       image="hub.hamdocker.ir/chrislusf/seaweedfs:3.61", 
                                       command=["weed", 'filer', f'-master=master-service.{ns}.svc.cluster.local:9333','-ip.bind=0.0.0.0','-metricsPort=9326','-s3'],
                                       ports=[k8s.ContainerPort(container_port=9326, name="metrics"),
                                              k8s.ContainerPort(container_port=8333, name="s3")],
                                       volume_mounts=[k8s.VolumeMount(mount_path="/etc/seaweedfs", name="filer-config")],
                                   )],
                                volumes=[k8s.Volume(name="filer-config", config_map=k8s.ConfigMapVolumeSource(name="filer-config"))]
                               )
                           )
                       )
                    )
        k8s.KubeService(self, "filer-service",
                        metadata=k8s.ObjectMeta(name="filer-service", namespace=ns),
                        spec=k8s.ServiceSpec(
                            ports=[k8s.ServicePort(port=9326, name="metrics"),
                                   k8s.ServicePort(port=8333, name="s3")],
                            selector={"app": "filer"}
                        )
                    )
        k8s.KubeDeployment(self, "master",
                           metadata=k8s.ObjectMeta(name="master-deployment", namespace=ns),
                       spec=k8s.DeploymentSpec(
                           replicas=1,
                           selector=k8s.LabelSelector(match_labels={"app": "master"}),
                           template=k8s.PodTemplateSpec(
                               metadata=k8s.ObjectMeta(labels={"app": "master"}),
                               spec=k8s.PodSpec(containers=[
                                   k8s.Container(
                                       name="master",
                                       image="hub.hamdocker.ir/chrislusf/seaweedfs:3.61", 
                                       command=["weed", "master", "-ip=master", "-ip.bind=0.0.0.0", "-metricsPort=9324", "-volumeSizeLimitMB=10", f"-defaultReplication=00{replica_count}", ],
                                       ports=[k8s.ContainerPort(container_port=9333, name="master"),
                                              k8s.ContainerPort(container_port=19333, name="volume"),
                                              k8s.ContainerPort(container_port=9324, name="metrics")],
                                   )],
                               )
                           )
                       )
            )
        k8s.KubeService(self, "master-service", 
                        metadata=k8s.ObjectMeta(name="master-service",namespace=ns),
                        spec=k8s.ServiceSpec(
                            ports=[k8s.ServicePort(port=9333, name="master"),
                                   k8s.ServicePort(port=19333, name="volume"),
                                   k8s.ServicePort(port=9324, name="metrics")],
                            selector={"app": "master"}
                        )
                    )
        k8s.KubeStatefulSet(self, "volume",
                            metadata=k8s.ObjectMeta(name="volume-deployment", namespace=ns),  
                          spec=k8s.StatefulSetSpec(
                            replicas=replica_count,
                            service_name="volume-service",
                            selector=k8s.LabelSelector(match_labels={"app": "volume"}),
                            template=k8s.PodTemplateSpec(
                                 metadata=k8s.ObjectMeta(labels={"app": "volume"}),
                                 spec=k8s.PodSpec(containers=[
                                      k8s.Container(
                                        name="volume",
                                        image="hub.hamdocker.ir/chrislusf/seaweedfs:3.61", 
                                        command=["weed", "volume", f"-mserver=master-service.{ns}.svc.cluster.local:9333", "-ip.bind=0.0.0.0", "-port=8080", "-metricsPort=9325", "-dir=/data"],
                                        volume_mounts=[k8s.VolumeMount(name="volume", mount_path="/data")],
                                      )]
                                 )
                            ),
                            volume_claim_templates=[k8s.KubePersistentVolumeClaimProps(
                                metadata=k8s.ObjectMeta(name="volume", namespace=ns),
                                spec=k8s.PersistentVolumeClaimSpec(
                                    access_modes=["ReadWriteOnce"],
                                    resources=k8s.ResourceRequirements(requests={"storage": k8s.Quantity.from_string(value="1Gi")})
                                )
                            )]
                        )
                    )
