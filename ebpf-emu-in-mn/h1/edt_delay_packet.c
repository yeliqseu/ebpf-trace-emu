#include <linux/bpf.h>
#include <bpf/bpf_helpers.h>
#include <linux/pkt_cls.h>
#include <linux/if_ether.h>
#include <linux/ip.h>
#include <linux/tcp.h>
#include <linux/udp.h>
#include <linux/in.h> // For IPPROTO_TCP and IPPROTO_UDP

#define bpf_htons(x)   __builtin_bswap16(x)
#define bpf_ntohs(x)   __builtin_bswap16(x)

#define FILTER_PORT_1 2112
#define FILTER_PORT_2 2112

#define TRACE_LEN 10000

struct {
    __uint(type, BPF_MAP_TYPE_ARRAY);
    __uint(max_entries, TRACE_LEN);
    __type(key, __u32);
    __type(value, __u32);
} delay_map_1 SEC(".maps");

static __u32 packet_index = 0;

SEC("delay_ebpf")
int edt_delay_packet(struct __sk_buff *skb) {
    void *data = (void *)(long)skb->data;
    void *data_end = (void *)(long)skb->data_end;
    struct ethhdr *eth = data; //Ethernet header
    __u64 nh_off = sizeof(struct ethhdr);
    __u32 key = packet_index % TRACE_LEN;

    if (data + nh_off > data_end) {
        return TC_ACT_OK;
    }

    // only ipv4 packets are processed
    if (eth->h_proto == bpf_htons(ETH_P_IP)) {
        struct iphdr *ip = data + nh_off;   // get the ip header
        nh_off += sizeof(*ip);      // update the offset
        if ((void*)ip + sizeof(*ip) > data_end) {
            return TC_ACT_OK;
        }

        // get the ports for the trasport layer protocol (tcp and udp)
        if (ip->protocol == IPPROTO_TCP || ip->protocol == IPPROTO_UDP) {
            __u16 *ports = NULL;

                ports = data + nh_off;


            if ((void*)ports + sizeof(__u16) * 2 > data_end) {
                return TC_ACT_OK;
            }
            //bpf_ntohs Network to Host Short 
            __u16 src_port = bpf_ntohs(ports[0]);
            __u16 dst_port = bpf_ntohs(ports[1]);

            // print port information
            //bpf_printk("IP protocol: %u, Src Port: %u, Dst Port: %u\n", 
            //           ip->protocol, src_port, dst_port);

            // only packets whose source or destination port is FILTER_PORT_1 or FILTER_PORT_2 are processed
            if (src_port == FILTER_PORT_1 || src_port == FILTER_PORT_2 ||
                dst_port == FILTER_PORT_1 || dst_port == FILTER_PORT_2) {
                __u32 key = packet_index % TRACE_LEN;
                __u32 *delay_ns;

                delay_ns = bpf_map_lookup_elem(&delay_map_1, &key);
                if (delay_ns) {
                    //bpf_printk("Delaying packet by %u ns\n", *delay_ns);

                    // get the current nanosecond timestamp
                    __u64 now = bpf_ktime_get_ns();

                    // set the departure : time current time + delay time
                    skb->tstamp = now + ((__u64) * delay_ns);

                    //update the packet_index 
                    packet_index++;
                    if (packet_index >= TRACE_LEN) {
                        packet_index = 0;
                    }

                } else {
                    //bpf_printk("Delay not found in map\n");
                }
            }
        }
    } else {
        //bpf_printk("Not an IPv4 packet\n");
    }

    return TC_ACT_OK;
}

char _license[] SEC("license") = "GPL";
