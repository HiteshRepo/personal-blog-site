---
title: 'Tricky gRPC load balancing'
date: 2023-05-24
summary: 'Emulates and resolves load balancing problems with gRPC'
---

gRPC has many benefits, like:

1. Multiplexes many requests using same connection.
2. Support for typical client-server request-response as well as duplex streaming.
3. Usage of a fast, very light, binary protocol with structured data as the communication medium among services.

[More about gRPC](https://www.infracloud.io/blogs/understanding-grpc-concepts-best-practices/)

All above make gRPC a very attractive deal but there is some consideration with gRPC particularly load balancing.

## The issue

Lets delve deep into the issue.

For this we will require a setup. The setup includes below:

- a gRPC server, we call it `Greet Server`.
- a client that acts as a REST gateway and internally it is a gRPC client as well. We call it `Greet Client`.

We are also using kubernetes for the demonstration, hence there are a bunch of YAML manifest files. Let me explain them below:

<details> <summary> greetserver-deploy.yaml </summary>

```yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: greetserver-deploy
spec:
  replicas: 3
  selector:
    matchLabels:
      run: greetserver
  template:
    metadata:
      labels:
        run: greetserver
    spec:
      containers:
        - image: hiteshpattanayak/greet-server:1.0
          imagePullPolicy: IfNotPresent
          name: greetserver
          ports:
            - containerPort: 50051
          env:
            - name: POD_IP
              valueFrom:
                fieldRef:
                  fieldPath: status.podIP
            - name: POD_NAME
              valueFrom:
                fieldRef:
                  fieldPath: metadata.name
```

</details>

The above is a deployment mainfest of `Greet Server`, that spins up 3 replicas of `Greet Server`.
The `Greet Server` uses `hiteshpattanayak/greet-server:1.0` image.
Also each pod of the deployment exposes `50051` port.
Environment variables: POD_IP and POD_NAME are injected into the pods.

What does each pod in the above server do?

They expose an `rpc` or service that expects a `first_name` and a `last_name`, in response they return a message in this format:
`reponse from Greet rpc: Hello, <first_name> <last_name> from pod: name(<pod_name>), ip(<pod_ip>).`

From the response, we can deduce which pod did our request land in.

greet.svc.yaml

```yml
apiVersion: v1
kind: Service
metadata:
  labels:
    run: greetserver
  name: greetserver
  namespace: default
spec:
  ports:
    - name: grpc
      port: 50051
      protocol: TCP
      targetPort: 50051
  selector:
    run: greetserver
```

The above is a service manifest of `Greet server service`. This basically acts as a proxy to above `Greet Server` pods.

The `selector` section of the service matches with the `labels` section of each pod.

greetclient-deploy.yaml

```yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: greetclient-deploy
spec:
  replicas: 1
  selector:
    matchLabels:
      run: greetclient
  template:
    metadata:
      labels:
        run: greetclient
    spec:
      containers:
        - image: hiteshpattanayak/greet-client:4.0
          name: greetclient
          ports:
            - containerPort: 9091
          env:
            - name: GRPC_SERVER_HOST
              value: greetserver.default.svc.cluster.local
            - name: GRPC_SVC
              value: greetserver
            - name: POD_NAMESPACE
              valueFrom:
                fieldRef:
                  fieldPath: metadata.namespace
```

The above is a deployment mainfest of `Greet Client`, that spins up 1 replica of `Greet Client`.

As mentioned above the pod runs an applications that acts as a rest gateway and reaches out to `Greet Server` in order to process the request.

This deployment is using `hiteshpattanayak/greet-client:4.0` image.

The `4.0` tagged image has the load balancing issue.

Also the pod(s) expose port `9091`.

greetclient-svc.yaml

```yml
apiVersion: v1
kind: Service
metadata:
  labels:
    run: greetclient
  name: greetclient
  namespace: default
spec:
  ports:
    - name: restgateway
      port: 9091
      protocol: TCP
      targetPort: 9091
  selector:
    run: greetclient
  type: LoadBalancer
```

The above service is just to redirect traffic to the `Greet Client` pods.

greet-ingress.yaml

```yml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: greet-ingress
  namespace: default
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "false"
spec:
  rules:
    - host: greet.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: greetclient
                port:
                  name: restgateway
```

The above ingress is to expose `Greet Client Service` to outside of the cluster.

Note:
`minikube` by default does not have ingress enabled by default

- check enabled or not: `minikube addons list`
- enable ingress addon: `minikube addons enable ingress`

greet-clusterrole.yaml

```yml
kind: ClusterRole
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  namespace: default
  name: service-reader
rules:
  - apiGroups: [""]
    resources: ["services"]
    verbs: ["get", "watch", "list"]
```

greet-clusterrolebinding.yaml

```yml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: service-reader-binding
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: service-reader
subjects:
  - kind: ServiceAccount
    name: default
    namespace: default
```

The cluster role and cluster role binding are required because the `default` service account does not have permission to fetch service details.
And the greet client pod internally tries to fetch service details, hence the binding is required.

Create the setup in below sequence:

```bash

kubectl create -f greet-clusterrole.yaml

kubectl create -f greet-clusterrolebinding.yaml

kubectl create -f greetserver-deploy.yaml

kubectl get po -l 'run=greetserver' -o wide
<<com
NAME                                  READY   STATUS    RESTARTS   AGE   IP           NODE       NOMINATED NODE   READINESS GATES
greetserver-deploy-7595ccbdd5-67bmd   1/1     Running   0          91s   172.17.0.4   minikube   <none>           <none>
greetserver-deploy-7595ccbdd5-k6zbl   1/1     Running   0          91s   172.17.0.3   minikube   <none>           <none>
greetserver-deploy-7595ccbdd5-l8kmv   1/1     Running   0          91s   172.17.0.2   minikube   <none>           <none>
com

kubectl create -f greet.svc.yaml
kubectl get svc
<<com
NAME          TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)     AGE
greetserver   ClusterIP   None         <none>        50051/TCP   77s
com

kubectl create -f greetclient-deploy.yaml
kubectl get po -l 'run=greetclient' -o wide
<<com
NAME                                 READY   STATUS    RESTARTS   AGE   IP           NODE       NOMINATED NODE   READINESS GATES
greetclient-deploy-6bddb94df-jwr25   1/1     Running   0          35s   172.17.0.6   minikube   <none>           <none>
com

kubectl create -f greet-client.svc.yaml
kubectl get svc
<<com
NAME          TYPE           CLUSTER-IP       EXTERNAL-IP   PORT(S)          AGE
greetclient   LoadBalancer   10.110.255.115   <pending>     9091:32713/TCP   22s
greetserver   ClusterIP      None             <none>        50051/TCP        5m14s
com

kubectl create -f greet-ingress.yaml
kubectl get ingress
<<com
NAME            CLASS   HOSTS       ADDRESS        PORTS   AGE
greet-ingress   nginx   greet.com   192.168.49.2   80      32s
com
```

since we have exposed the `Greet Client` to outside of cluster via `greet-ingress`, the endpoint can be accessed on: `http://greet.com/greet`.
so when we make a curl request:

Request#1

```bash
curl --request POST \
  --url http://greet.com/greet \
  --header 'Content-Type: application/json' \
  --data '{
 "first_name": "Hitesh",
 "last_name": "Pattanayak"
}'

<<com
Response

reponse from Greet rpc: Hello, Hitesh Pattanayak from pod: name(greetserver-deploy-7595ccbdd5-l8kmv), ip(172.17.0.2).
com
```

Request#2

```bash
curl --request POST \
  --url http://greet.com/greet \
  --header 'Content-Type: application/json' \
  --data '{
 "first_name": "Hitesh",
 "last_name": "Pattanayak"
}'

<<com
Response

reponse from Greet rpc: Hello, Hitesh Pattanayak from pod: name(greetserver-deploy-7595ccbdd5-l8kmv), ip(172.17.0.2).
com
```

Request#3

```bash
curl --request POST \
  --url http://greet.com/greet \
  --header 'Content-Type: application/json' \
  --data '{
 "first_name": "Hitesh",
 "last_name": "Pattanayak"
}'

<<com
Response

reponse from Greet rpc: Hello, Hitesh Pattanayak from pod: name(greetserver-deploy-7595ccbdd5-l8kmv), ip(172.17.0.2).
com
```

So the ISSUE is no matter hw many request I make, the request lands up in the same server. This is happending because of sticky nature of HTTP/2.
The advantage of gRPC becomes it own peril.

The codebase to replicate the issue can be found [in this commit](https://github.com/HiteshRepo/grpc-loadbalancing/commit/dd31d2628d4ee1e47b07b5737ff51cfc43c76d4e).

## gRPC Client side load balancing

We have discussed earlier about one of the challenges with gRPC which is load balancing.

That happens due to the sticky nature of gRPC connections.

Now we shall discuss how to resolve the issue.

This particular solution is quite simple.

The onus to load balance falls on the client itself.

To be particular, client does not mean end user. All gRPC servers have a REST gateway that is used by end users.

This is because HTTP2, which is the protocol used by gRPC, is yet to have browser support.

Hence the REST gateway acts as a gRPC client to gRPC servers. And thats why gRPC is mostly used for internal communications.

Earlier we had used `hiteshpattanayak/greet-client:4.0` image for `Greet Client` which had the normal gRPC setup without client side load balancing.
The code can be referred [in this commit](https://github.com/HiteshRepo/grpc-loadbalancing/commit/dd31d2628d4ee1e47b07b5737ff51cfc43c76d4e).

## Changes

### Code changes

For this solution we use `hiteshpattanayak/greet-client:11.0` image. The [codebase](https://github.com/HiteshRepo/grpc-loadbalancing/pull/1/files) has below changes:

Updated client deployment manifest:

```yml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: greetclient-deploy
spec:
  replicas: 1
  selector:
    matchLabels:
      run: greetclient
  template:
    metadata:
      labels:
        run: greetclient
    spec:
      containers:
        - image: hiteshpattanayak/greet-client:11.0
          name: greetclient
          ports:
            - containerPort: 9091
          env:
            - name: GRPC_SVC
              value: greetserver
            - name: POD_NAMESPACE
              valueFrom:
                fieldRef:
                  fieldPath: metadata.namespace
```

- configuring load balancing policy while making dialing to the server.
- configuring to terminate connection while dialing to the server.

```go
a.conn, err = grpc.Dial(
  servAddr,
  grpc.WithDefaultServiceConfig(`{"loadBalancingPolicy":"round_robin"}`),
  grpc.WithBlock(),
  opts,
 )
```

- the server address used while dialing needs to the dns address of the server.

```go
var serverHost string
if host := kubernetes.GetServiceDnsName(client, os.Getenv("GRPC_SVC"), os.Getenv("POD_NAMESPACE")); len(host) > 0 {
  serverHost = host
 }

servAddr := fmt.Sprintf("%s:%s", serverHost, serverPort)
```

### Headless service

- also earlier while replicating the issue the service (greetserver) we created for `Greet server pods` was of normal `ClusterIP` type. The headless ClusterIP service is required for this solution.

```yml
apiVersion: v1
kind: Service
metadata:
  labels:
    run: greetserver
  name: greetserver
  namespace: default
spec:
  ports:
    - name: grpc
      port: 50051
      protocol: TCP
      targetPort: 50051
  selector:
    run: greetserver
  clusterIP: None
```

One significant thing to notice over here is that this is a special type of `ClusterIP` service called `Headless` service.

In this `service` kind, the type of service is not specified. By default the type becomes `ClusterIP`. Which means the service becomes available within cluster.

You can set `.spec.clusterIP`, if you already have an existing DNS entry that you wish to reuse.

In case you set `.spec.clusterIP` to `None`, it makes the service `headless`, which means when a client sends a request to a headless Service, it will get back a list of all Pods that this Service represents (in this case, the ones with the label `run: greetserver`).

Kubernetes allows clients to discover pod IPs through DNS lookups. Usually, when you perform a DNS lookup for a service, the DNS server returns a single IP — the service’s cluster IP. But if you tell Kubernetes you don’t need a cluster IP for your service (you do this by setting the clusterIP field to None in the service specification ), the DNS server will return the pod IPs instead of the single service IP.
Instead of returning a single DNS A record, the DNS server will return multiple A records for the service, each pointing to the IP of an individual pod backing the service at that moment. Clients can therefore do a simple DNS A record lookup and get the IPs of all the pods that are part of the service. The client can then use that information to connect to one, many, or all of them.

Basically, the Service now lets the client decide on how it wants to connect to the Pods.

#### Verify headless service DNS lookup

create the headless service:

```bash
kubectl create -f greet.svc.yaml
```

create an utility pod:

```bash
kubectl run dnsutils --image=tutum/dnsutils --command -- sleep infinity
```

verify by running `nslookup` command on the pod

```bash
kubectl exec dnsutils --  nslookup greetserver

<<com
Result

Server:         10.96.0.10
Address:        10.96.0.10#53
Name:   greetserver.default.svc.cluster.local
Address: 172.17.0.4
Name:   greetserver.default.svc.cluster.local
Address: 172.17.0.3
Name:   greetserver.default.svc.cluster.local
Address: 172.17.0.2
```

As you can see headless service resolves into the IP address of all pods connected through service.

Contrast this with the output returned for non-headless service.

```bash
kubectl exec dnsutils --  nslookup greetclient

<<com
Server:  10.96.0.10
Address: 10.96.0.10#53

Name: greetclient.default.svc.cluster.local
Address: 10.110.255.115
com
```

Now lets test the changes by making curl requests to the exposed ingress.

Request#1

```bash
curl --request POST \
  --url http://greet.com/greet \
  --header 'Content-Type: application/json' \
  --data '{
 "first_name": "Hitesh",
 "last_name": "Pattanayak"
}'

<<com
Response

reponse from Greet rpc: Hello, Hitesh Pattanayak from pod: name(greetserver-deploy-7595ccbdd5-k6zbl), ip(172.17.0.3).
com
```

Request#2

```bash
curl --request POST \
  --url http://greet.com/greet \
  --header 'Content-Type: application/json' \
  --data '{
 "first_name": "Hitesh",
 "last_name": "Pattanayak"
}'

<<com
Response

reponse from Greet rpc: Hello, Hitesh Pattanayak from pod: name(greetserver-deploy-7595ccbdd5-67bmd), ip(172.17.0.4).
com
```

Request#3

```bash
curl --request POST \
  --url http://greet.com/greet \
  --header 'Content-Type: application/json' \
  --data '{
 "first_name": "Hitesh",
 "last_name": "Pattanayak"
}'

<<com
Response

reponse from Greet rpc: Hello, Hitesh Pattanayak from pod: name(greetserver-deploy-7595ccbdd5-l8kmv), ip(172.17.0.2).
com
```

The issue no longer exists.

But what we are losing here is the capability of gRPC to retain connections for a longer period of time and multiplex several requests through them thereby reducing latency.

## gRPC lookaside load balancing

Earlier we discussed about:

- Load balancing challenge with gRPC
- How to address the above challenge via client side load balancing

Even though we were able to resolve the load balancing issue but we traded off one of the major advantage of gRPC which is long duration connections.

So in this post we would like the achive load balancing (still client side) but we are gonna not trade off the above mentionde gRPC's advantage.

I would like to re-iterate when I say onus to load balance falls on `client side`, client does not mean end user. All gRPC servers have a REST gateway that is used by end users. gRPC services are not directly exposed because of lack of browser support.

## Lookaside load balancer

The purpose of this load balancer is to resolve which gRPC server to connect.

At the moment this load balancer works in two ways: round robin and random.

Load balancer itself is gRPC based and since the load is not going to be too much only one pod would suffice.

It exposes a service called `lookaside` and an rpc called `Resolve` which expects the type of routing along with some details about the gRPC servers like kubernetes service name and namespace they exist in.

Using the service name and namespace, it is going to fetch kubernetes endpoints object associated with it. From the endpoint object server IPs can be found.
Those IPs are going to be stored in memory. Every now and then those IPs would be refreshed based on interval set. For every request to resolve IP, it is going to rotate the IPs based on the routing type in the request.

Code for lookaside load balancer can be found [in this branch](https://github.com/HiteshRepo/grpc-loadbalancing/tree/lookaside/internal/app/lookaside).

We are using the image `hiteshpattanayak/lookaside:9.0` for lookaside pod.

The pod manifest would be like this:

```yml
apiVersion: v1
kind: Pod
metadata:
  labels:
    run: lookaside
  name: lookaside
  namespace: default
spec:
  containers:
    - image: hiteshpattanayak/lookaside:9.0
      name: lookaside
      ports:
        - containerPort: 50055
      env:
        - name: LB_PORT
          value: "50055"
```

since it is too a gRPC server, the exposed port is `50055`.

The service manifest that exposes the pod is as below:

```yml
apiVersion: v1
kind: Service
metadata:
  labels:
    run: lookaside-svc
  name: lookaside-svc
  namespace: default
spec:
  ports:
    - port: 50055
      protocol: TCP
      targetPort: 50055
  selector:
    run: lookaside
  clusterIP: None
```

I chose `headless` service for this as well but there is no such need for this.

Updated the `ClusterRole` to include ability to fetch `endpoints` and `pod` details

```yml
kind: ClusterRole
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  namespace: default
  name: service-reader
rules:
  - apiGroups: [""]
    resources: ["services", "pods", "endpoints"]
    verbs: ["get", "watch", "list"]
```

## Changes with Greet Client

`Greet Client` is now [integrated](https://github.com/HiteshRepo/grpc-loadbalancing/blob/177c0fdccad06a76d7d6ce221ee267a47244dc43/internal/app/greetclient/app.go#L38) with lookaside loadbalancer.

The client is [set](https://github.com/HiteshRepo/grpc-loadbalancing/blob/177c0fdccad06a76d7d6ce221ee267a47244dc43/internal/app/greetclient/app.go#L131) to use `RoundRobin` routing type but can be made configurable via configmap or environment variables.

Removed setting `load-balancing` policy and forcefully terminating connection by setting `WithBlock` option while dialing.

from

```go
conn, err := grpc.Dial(
    servAddr,
    grpc.WithDefaultServiceConfig(`{"loadBalancingPolicy":"round_robin"}`),
    grpc.WithBlock(),
    opts,
)
```

to

```go
conn, err := grpc.Dial(
    servAddr,
    opts,
)
```

So how does it solve the earlier load balancing problem where we traded off terminating long duration connections for the sake of load balancing.

What we did was to store the previous connections to the server and reuse it but rotate for each request.

```go
if c, ok := a.greetClients[host]; !ok {
    servAddr := fmt.Sprintf("%s:%s", host, serverPort)

    fmt.Println("dialing greet server", servAddr)

    conn, err := grpc.Dial(
        servAddr,
        opts,
    )
    if err != nil {
        log.Printf("could not connect greet server: %v", err)
        return err
    }

    a.conn[host] = conn

    a.currentGreetClient = proto.NewGreetServiceClient(conn)
    a.greetClients[host] = a.currentGreetClient
} else {
    a.currentGreetClient = c
}
```

### Conclusion

gRPC is a great solution for microservice internal communication because of efficiency, speed and parity. But the long duration connections though an advantage results in tricky load balancing. With the help of this article we found ways to handle it.

There are ways to handle via service meshes like Linkerd and Istio. But it would be handy to have solutions incase where service meshes are not setup.

Folks, if you like my content, would you consider following me on [LinkedIn](https://www.linkedin.com/in/hitesh-pattanayak-52290b160/).
