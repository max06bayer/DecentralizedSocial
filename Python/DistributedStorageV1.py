import socket
import requests
import json
import time
from threading import Thread
import hashlib
import os
import random

class Node:
    def __init__(self, port:int, bootstrapNodes:list):
        # initialize the network
        self.publicIP = requests.get('https://api.ipify.org').content.decode('utf8')
        if self.publicIP in bootstrapNodes: bootstrapNodes.remove(self.publicIP)
        self.localIP = self.get_local_ip()
        self.port = port
        self.pendingResponse = None

        # initialize the Storage
        self.DHT = [[] for bucket in range(160)]
        self.CID = hashlib.sha1(os.urandom(20)).hexdigest()
        self.bootstrapIPs = bootstrapNodes

        # run server & bootstrapping in parallel
        Thread(target=self.receiveData).start()
        Thread(target=self.bootstrap).start()

    def bootstrap(self):
        while True:
            time.sleep(1)
            bucketTargets = []
            for i in range(160):
                targetCID = self.generateTargetCID(i)
                bucketTargets.append(targetCID)
            
            # Fill up the DHT with the bootstrap nodes
            for node in self.bootstrapIPs:
                self.sendData(node, {'nodeInfoRequest': (self.publicIP, self.CID)})
                
            # Lookup the closest node for each Bucket Range
            for index, bucket in enumerate(bucketTargets):
                closestNodes = self.deepNodeSearch(bucket, 5)
                for node in closestNodes:
                    print(f"Looking to fill bucket {index}", end="\r")
                    if self.getBucketIndex(next(iter(dict(node)))) == index: 
                        print(f"\nFound Node {node} in bucket {index}")
                        self.addNode(node[next(iter(dict(node)))], next(iter(dict(node))))


    def getClosestCIDs(self, cid, amount=16) -> list:
        all_nodes = []
        for bucket in self.DHT:
            for node in bucket:
                all_nodes.append(node)

        all_nodes.sort(key=lambda node: int(next(iter(dict(node))), base=16) ^ int(cid, base=16))
        return all_nodes[:amount]
    
    def askForClosestNodes(self, cid, targetNodeIP):
        # Ask the target node for its closest nodes to cid
        data = {'closestNodesRequest': (self.publicIP, cid)}
        self.sendData(targetNodeIP, data)
        while self.pendingResponse == None:
            time.sleep(1)

        return self.pendingResponse


    def deepNodeSearch(self, cid, amount):
        # Keep track of k closest nodes we've seen
        closest_nodes = []
        asked_nodes = []
        
        # Start with closest nodes from our buckets
        closest_nodes = self.getClosestCIDs(cid, amount=20)
        closest_distance = float('inf')
        
        while True:
            next_to_ask = None
            for node in closest_nodes:
                if node not in asked_nodes:
                    distance = int(int(next(iter(dict(node))), base=16) ^ int(cid, base=16)).bit_length() - 1
                    if distance < closest_distance:
                        next_to_ask = node
                        closest_distance = distance
            
            # If we've asked all nodes or no closer nodes found, we're done
            if not next_to_ask:
                break
                
            # Ask this node for its closest nodes
            asked_nodes.append(next_to_ask)
            new_nodes = self.askForClosestNodes(cid, next_to_ask[next(iter(dict(next_to_ask)))])
            self.pendingResponse = None
            
            # Update our list of closest nodes
            all_nodes = closest_nodes + new_nodes
            all_nodes.sort(key=lambda node: int(next(iter(dict(node))), base=16) ^ int(cid, base=16))
            closest_nodes = all_nodes[:amount]
            
            # Update closest distance we've seen
            new_closest = int(next(iter(dict(closest_nodes[0]))), base=16) ^ int(cid, base=16)
            if new_closest >= closest_distance:
                break
            closest_distance = new_closest

        return closest_nodes[:amount]


    def get_local_ip(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server.connect(('8.8.8.8', 80)); local_ip = server.getsockname()[0];
        server.close(); return local_ip
    
    def getBucketIndex(self, otherCid: str):
        # Finds in which bucket the other_cid belongs
        hash_0 = int(self.CID, base=16)
        hash_1 = int(otherCid, base=16)
        distance = hash_0 ^ hash_1
        return distance.bit_length() - 1

    def addNode(self, ip: str, cid: str):
        # Adds the node to the DHT
        dht_index = self.getBucketIndex(cid)
        self.DHT[dht_index].append({cid:ip})

    def receiveData(self):
        # Start the server
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind((self.localIP, self.port)); listener.listen(5)
        print(f"Started FileSytem Node on IP: {self.publicIP}, PORT: {self.port}, CID: {self.CID}")

        while True:
            clientSocket, clientAddress = listener.accept()
            data = json.loads(clientSocket.recv(1024).decode("utf-8"))
            # Handle the incoming data

            if 'nodeInfoRequest' in data:
                self.addNode(data['nodeInfoRequest'][0], data['nodeInfoRequest'][1])
                self.sendData(data['nodeInfoRequest'][0], {'nodeInfoResponse': (self.publicIP, self.CID)})

            elif 'nodeInfoResponse' in data:
                self.addNode(data['nodeInfoResponse'][0], data['nodeInfoResponse'][1])

            elif 'closestNodesRequest' in data:
                self.sendData(data['closestNodesRequest'][0], 
                    {'closestNodesResponse': self.getClosestCIDs(data['closestNodesRequest'][1], 20)})
                
            elif 'closestNodesResponse' in data:
                self.pendingResponse = data['closestNodesResponse']


    def sendData(self, ip:str, data:dict):
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((ip, self.port))
        data = json.dumps(data, indent = 4)
        client.send(data.encode("utf-8"))
        client.close()

    def generateTargetCID(self, bucketDistance: int) -> str:
        myCidInt = int(self.CID, 16)
        lowerBound = 2 ** bucketDistance
        upperBound = 2 ** (bucketDistance + 1) - 1
        distance = random.randint(lowerBound, upperBound)
        targetInt = myCidInt ^ distance
        return format(targetInt, '040x')
    
    def showDHT(self):
        # Print the DHT
        # os.system('clear')
        for i, bucket in enumerate(self.DHT):
            if len(bucket) == 0: continue
            print(f"Bucket {i}: ", end="")
            for node in bucket:
                print(f"{node} ", end="")
            print()

    
myNode = Node(port=60000, bootstrapNodes=['79.230.223.138']);
while True: 
    time.sleep(5); # myNode.showDHT()