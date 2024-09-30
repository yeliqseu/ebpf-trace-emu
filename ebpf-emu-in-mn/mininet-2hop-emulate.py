
#!/usr/bin/python
'''
Created on Mon Sep 30 2024
author: yeli , Weibiao Tian
script: deploy the delay_ebpf and loss_ebpf program on Mininet
topo:
h1-eth0 -- h2-eth0
'''

from mininet.net import Mininet
from mininet.node import Controller
from mininet.cli import CLI
from mininet.link import TCLink  # importing TCLink for custom link characteristics
from mininet.log import setLogLevel, info

def deploy_ebpf():
    net = Mininet(link=TCLink)

    info('*** Adding controller\n')
    net.addController('c0')

    info('*** Adding hosts\n')
    h1 = net.addHost('h1', ip='10.0.0.1')
    h2 = net.addHost('h2', ip='10.0.0.2')

    info('*** Creating link\n')
    net.addLink(h1, h2)

    info('*** Starting network\n')
    net.start()

    info('*** Setting up TC filter with eBPF program\n')
    # Attach eBPF program to interface of the first host
    h1.cmd('cd h1/')
    h1.cmd('sudo mount -t bpf bpf /sys/fs/bpf/')
    h1.cmd('sudo clang -O2 -g -target bpf -c edt_delay_packet.c -o edt_delay_packet.o')
    h1.cmd('sudo tc qdisc add dev h1-eth0 clsact')
    h1.cmd('sudo tc filter add dev h1-eth0 egress bpf direct-action obj edt_delay_packet.o sec delay_ebpf')
    h1.cmd('sudo tc qdisc add dev h1-eth0 root fq')
 
    #h1.cmd('mount -t bpf bpf /sys/fs/bpf/')
    h1.cmd('sudo clang -O2 -g -target bpf -c xdp_drop_packet.c -o xdp_drop_packet.o')
    h1.cmd('sudo ip link set dev h1-eth0 xdpgeneric obj xdp_drop_packet.o sec xdp_port_filter')


    # Attach eBPF program to interface of the second host
    h2.cmd('cd h2/')
    h2.cmd('sudo mount -t bpf bpf /sys/fs/bpf/')
    h2.cmd('sudo clang -O2 -g -target bpf -c edt_delay_packet.c -o edt_delay_packet.o')
    h2.cmd('sudo tc qdisc add dev h2-eth0 clsact')
    h2.cmd('sudo tc filter add dev h2-eth0 egress bpf direct-action obj edt_delay_packet.o sec delay_ebpf')
    h2.cmd('sudo tc qdisc add dev h2-eth0 root fq')
 

    #h2.cmd('mount -t bpf bpf /sys/fs/bpf/')
    h2.cmd('sudo clang -O2 -g -target bpf -c xdp_drop_packet.c -o xdp_drop_packet.o')
    h2.cmd('sudo ip link set dev h2-eth0 xdpgeneric obj xdp_drop_packet.o sec xdp_port_filter')

    
    info('*** Running CLI\n')
    CLI(net)

    info('*** Stopping network\n')
    net.stop()

def ebpf_environment_set():
    # install the essential components
    pass


if __name__ == '__main__':
    setLogLevel('info')
    deploy_ebpf()