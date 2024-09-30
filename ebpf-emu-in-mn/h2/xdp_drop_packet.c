#include <linux/bpf.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/tcp.h>
#include <linux/udp.h>
#include <bpf/bpf_helpers.h>
#include <linux/in.h>

#define bpf_htons(x)   __builtin_bswap16(x)
#define bpf_ntohs(x)   __builtin_bswap16(x)

#define FILTER_PORT_1 2112 
#define FILTER_PORT_2 2112 

#define TRACE_LEN 10000

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, TRACE_LEN);
    __type(key, __u32);
    __type(value, int);
} loss_map_2 SEC(".maps");

static __u32 packet_index = 0;

SEC("xdp_port_filter")
int xdp_drop_packet(struct xdp_md *ctx) {
    void *data_end = (void *)(long)ctx->data_end;
    void *data = (void *)(long)ctx->data;

    struct ethhdr *eth = data;
    if ((void *)(eth + 1) > data_end || eth->h_proto != bpf_htons(ETH_P_IP)) {
        return XDP_PASS;
    }

    struct iphdr *iph = data + sizeof(struct ethhdr);
    if ((void *)(iph + 1) > data_end) {
        return XDP_PASS;
    }

    // only ipv4 packets are processed
    if (iph->protocol != IPPROTO_TCP && iph->protocol != IPPROTO_UDP) {
        return XDP_PASS;
    }

    __u64 offset = sizeof(struct ethhdr) + iph->ihl * 4;
    __u16 sport = 0, dport = 0;
    __u16 *ports;

    // extract the source and destination ports
    if (iph->protocol == IPPROTO_TCP || iph->protocol == IPPROTO_UDP) {
        ports = data + offset;

        // check if the packet is complete
        if ((void *)(ports + 2) > data_end) {
            return XDP_PASS;
        }

        // bpf_ntohs Network to Host Short 
        sport = bpf_ntohs(ports[0]);
        dport = bpf_ntohs(ports[1]);
    }

    // Checks if the port matches the filtering criteria
    if (sport == FILTER_PORT_1 || sport == FILTER_PORT_2 || dport == FILTER_PORT_1 || dport == FILTER_PORT_2) {
        __u32 key = packet_index % TRACE_LEN;
        int *trace_value = bpf_map_lookup_elem(&loss_map_2, &key);

        if (!trace_value) {
            bpf_printk("Key %u not found\n", key);
            return XDP_PASS;
        }

        //bpf_printk("Packet at index %u with key %u has trace_value %d\n", packet_index, key, *trace_value);

        if (*trace_value) {
            //bpf_printk("Dropping %s Packet: Source Port: %u, Dest Port: %u\n",
            //           (iph->protocol == IPPROTO_TCP) ? "TCP" : "UDP", sport, dport);
            packet_index = (packet_index + 1) % TRACE_LEN;
            return XDP_DROP;
        } else {
            //bpf_printk("Passing %s Packet: Source Port: %u, Dest Port: %u\n",
            //          (iph->protocol == IPPROTO_TCP) ? "TCP" : "UDP", sport, dport);
            packet_index = (packet_index + 1) % TRACE_LEN;
        }
    }

    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";
