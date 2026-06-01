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
#define TRACE_INTERVAL_NS 10000000ULL // 10ms

#define MODE_PACKET_DRIVEN 0
#define MODE_TIME_DRIVEN   1

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, 1);
    __type(key, __u32);
    __type(value, __u32);
} config_map SEC(".maps");

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, TRACE_LEN);
    __type(key, __u32);
    __type(value, int);
} loss_map_1 SEC(".maps");

static __u32 packet_index = 0;
static __u64 start_time = 0;

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

    if (iph->protocol != IPPROTO_TCP && iph->protocol != IPPROTO_UDP) {
        return XDP_PASS;
    }

    __u64 offset = sizeof(struct ethhdr) + iph->ihl * 4;
    __u16 sport = 0, dport = 0;
    __u16 *ports;

    if (iph->protocol == IPPROTO_TCP || iph->protocol == IPPROTO_UDP) {
        ports = data + offset;

        if ((void *)(ports + 2) > data_end) {
            return XDP_PASS;
        }

        sport = bpf_ntohs(ports[0]);
        dport = bpf_ntohs(ports[1]);
    }

    if (sport == FILTER_PORT_1 || sport == FILTER_PORT_2 || dport == FILTER_PORT_1 || dport == FILTER_PORT_2) {
        
        __u32 config_key = 0;
        __u32 *mode_ptr = bpf_map_lookup_elem(&config_map, &config_key);
        __u32 current_mode = mode_ptr ? *mode_ptr : MODE_PACKET_DRIVEN;

        __u32 trace_key = 0;
        __u64 now = bpf_ktime_get_ns();

        if (current_mode == MODE_TIME_DRIVEN) {
            if (start_time == 0) {
                start_time = now;
            }
            __u64 elapsed = now - start_time;
            trace_key = (elapsed / TRACE_INTERVAL_NS) % TRACE_LEN;
        } else {
            trace_key = packet_index % TRACE_LEN;
        }

        int *trace_value = bpf_map_lookup_elem(&loss_map_1, &trace_key);

        if (!trace_value) {
            return XDP_PASS;
        }

        if (*trace_value) {
            if (current_mode == MODE_PACKET_DRIVEN) {
                packet_index = (packet_index + 1) % TRACE_LEN;
            }
            return XDP_DROP;
        } else {
            if (current_mode == MODE_PACKET_DRIVEN) {
                packet_index = (packet_index + 1) % TRACE_LEN;
            }
        }
    }

    return XDP_PASS;
}

char _license[] SEC("license") = "GPL";