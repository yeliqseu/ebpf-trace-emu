#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>
#include <linux/pkt_cls.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/tcp.h>
#include <linux/udp.h>
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
    __type(value, __u32);
} delay_map_1 SEC(".maps");

static __u32 packet_index = 0;
static __u64 start_time = 0;

SEC("delay_ebpf")
int edt_delay_packet(struct __sk_buff *skb) {
    void *data = (void *)(long)skb->data;
    void *data_end = (void *)(long)skb->data_end;
    struct ethhdr *eth = data;
    __u64 nh_off = sizeof(struct ethhdr);

    if (data + nh_off > data_end) {
        return TC_ACT_OK;
    }

    if (eth->h_proto == bpf_htons(ETH_P_IP)) {
        struct iphdr *ip = data + nh_off;
        nh_off += sizeof(*ip);
        if ((void*)ip + sizeof(*ip) > data_end) {
            return TC_ACT_OK;
        }

        if (ip->protocol == IPPROTO_TCP || ip->protocol == IPPROTO_UDP) {
            __u16 *ports = data + nh_off;
            if ((void*)ports + sizeof(__u16) * 2 > data_end) {
                return TC_ACT_OK;
            }

            __u16 src_port = bpf_ntohs(ports[0]);
            __u16 dst_port = bpf_ntohs(ports[1]);

            if (src_port == FILTER_PORT_1 || src_port == FILTER_PORT_2 ||
                dst_port == FILTER_PORT_1 || dst_port == FILTER_PORT_2) {
                
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

                __u32 *delay_ns = bpf_map_lookup_elem(&delay_map_1, &trace_key);
                if (delay_ns) {
                    skb->tstamp = now + ((__u64) * delay_ns);

                    if (current_mode == MODE_PACKET_DRIVEN) {
                        packet_index++;
                        if (packet_index >= TRACE_LEN) {
                            packet_index = 0;
                        }
                    }
                }
            }
        }
    }

    return TC_ACT_OK;
}

char _license[] SEC("license") = "GPL";