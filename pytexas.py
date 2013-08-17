#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import os
import time

import pyrax
import pyrax.utils as utils
import pyrax.exceptions as exc

# If you have keyring configured...
pyrax.keyring_auth()
# If you have a credential file...
#pyrax.set_credential_file("/path/to/file")
# Or just set directly
#pyrax.set_credentials(username, password)

cs = pyrax.cloudservers
cf = pyrax.cloudfiles
clb = pyrax.cloud_loadbalancers
cdb = pyrax.cloud_databases
cnw = pyrax.cloud_networks
dns = pyrax.cloud_dns

start = time.time()
print "*" * 66
print "Starting at", time.ctime() 
print "*" * 66


# ID of appserver image
# This is hardcoded for demo purposes.
# DFW
image_id = "7789e8ca-b9df-495f-b47d-736a5f7b885a"
# IAD
#image_id = "5ed8bee1-4bf8-4247-aac6-ad7ed5b865a2"

def add_to_cleanup(svc, reso):
    filename = "pycondemo.json"
    cleanup = {}
    try:
        with open(filename) as ff:
            cleanup = json.load(ff)
    except IOError:
        pass
    try:
        cleanup[svc].append(reso.id)
    except (KeyError, AttributeError):
        cleanup[svc] = [reso.id]
    with open(filename, "w") as ff:
        json.dump(cleanup, ff)

# Create the database instance
# NOTE: The flavor ID and size are hardcoded
# for demo purposes.
print
print "Creating the database instance..."
db_instance = cdb.create("PyTexas_DB", flavor=1, volume=2)
utils.wait_for_build(db_instance, verbose=True)
db = db_instance.create_database("demodb")
add_to_cleanup("CDB", db_instance)
db_user = db_instance.create_user("demouser",
        "topsecret", db)
db_host = db_instance.hostname
print "Database instance created; hostname:", db_host

# Create the isolated network
print
print "Creating the isolated network"
new_network_name = "PyTexas_NW"
new_network_cidr = "192.168.0.0/24"
new_net = cnw.create(new_network_name,
        cidr=new_network_cidr)
add_to_cleanup("CNW", new_net)
print "Network created:", new_net

# Store the public key
keyfile = os.path.expanduser("~/.ssh/id_rsa.pub")
with open(keyfile, "r") as kf:
    pub = kf.read()
    key = cs.keypairs.create("macbook", pub)
    add_to_cleanup("CSK", key)

# Create two servers with only ServiceNet
networks = [{"net-id": cnw.SERVICE_NET_ID}]
print
print "Creating the two app servers"
server1 = cs.servers.create("PyTexas_Srv1",
        image=image_id, flavor=3, key_name="macbook",
        nics=networks)
server2 = cs.servers.create("PyTexas_Srv2",
        image=image_id, flavor=3, key_name="macbook",
        nics=networks)
add_to_cleanup("CS", server1)
add_to_cleanup("CS", server2)
utils.wait_for_build(server1, verbose=True)
utils.wait_for_build(server2, verbose=True)
print "App servers created."
print "Server 1:", server1.name, server1.addresses
print "Server 2:", server2.name, server2.addresses

# Get the server IPs
print
print "Creating the nodes"
ip1 = server1.addresses["private"][0]["addr"]
ip2 = server2.addresses["private"][0]["addr"]
# Define the nodes
node1 = clb.Node(address=ip1, port=80,
        weight=1, condition="ENABLED")
node2 = clb.Node(address=ip2, port=80,
        weight=1, condition="ENABLED")
print "Node 1 created:", node1
print "Node 2 created:", node2

# Create the Virtual IP
print
print "Creating the Virtual IP"
vip = clb.VirtualIP(type="PUBLIC")
print "Virtual IP:", vip

# Create the Load Balancer
print
print "Creating the Load Balancer"
lb = clb.create("PyTexas_LB", port=80, protocol="HTTP",
        nodes=[node1, node2], virtual_ips=vip,
        algorithm="WEIGHTED_ROUND_ROBIN")
add_to_cleanup("CLB", lb)
utils.wait_for_build(lb, verbose=True)
lb_ip = lb.virtual_ips[0].address
print "Load Balancer created:", lb
print
print "=" * 66
print "Load Balancer IP:", lb_ip
print "=" * 66

# Configure DNS to point to the LB
domain_name = "pyraxdemo.com"
print
print "Configuring DNS for the Load Balancer"
dom = dns.create(name=domain_name,
        emailAddress="ed.leafe@rackspace.com",
        ttl=900, comment="Pyrax Demo")
add_to_cleanup("DNS", dom)
a_rec = {"type": "A",
        "name": domain_name,
        "data": lb_ip,
        "ttl": 900}
recs = dom.add_record(a_rec)
print "DNS domain:", dom
print "Records:", recs

end = time.time()
elapsed = end - start
print
print
print "*" * 66
print "It took %6.2f seconds to build the infrastructure." % elapsed
print "*" * 66
print
print "Server 1 IP address:", ip1
print "Server 2 IP address:", ip2
print "Load Balancer IP address:", lb_ip
print
print
# Wait until we're ready
raw_input("Ready to add a third app server?")

# Add another node
print
print "Creating a third app server..."
server3 = cs.servers.create("PyTexas_Srv3",
        image=image_id, flavor=3, key_name="macbook",
        nics=networks)
add_to_cleanup("CS", server3)
utils.wait_for_build(server3, verbose=True)
print "Third app server created."
print "Server 3:", server3.name, server3.addresses
ip3 = server3.addresses["private"][0]["addr"]
node3 = clb.Node(address=ip3, port=80,
        weight=3, condition="ENABLED")
lb.add_nodes(node3)
print 
print "Third node added with a weight of 3"
print
print "*" * 66
print "Server 1 IP address:", ip1
print "Server 2 IP address:", ip2
print "Server 3 IP address:", ip3
print "Load Balancer IP address:", lb_ip
print "*" * 66
print
print
