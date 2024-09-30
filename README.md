# Introduction
This repository provides a Mininet environment to demonstrate an eBPF-based emulation method for replaying packet delay/loss traces of satellite networks. The repo includes an example trace collected from a Starlink testbed. 

__REMARK__: The use of Mininet here is only for conveniently testing out the emulation method over two virtual hosts on a local host. The method does not need any mechanism from Mininet. The eBPF-based emulation method can (and is supposed to) be deployed to real-life nodes of a physical network. Please see the commands of the Mininet scripts for the deployment details.

# The Mininet environment for eBPF-based Starlink emulation

Please ensure that the host of Mininet runs a Linux kernel version supporting eBPF features. Linux 5.11 or higher is recommended. The following procedures are tested on Ubuntu 22.04 with Linux 5.15.0-23-generic. The environment consists of two hosts as follows, where the uplink (h1->h2) and downlink propagation delays are emulated on `h1` and `h2` using `edt_delay_packet.o`, respectively, and the corresponding losses are emulated on `h2` and `h1` using `xdp_drop_packet.o`, repsectively. 

```
        +--------+                                      +--------+
        |   h1   |                                      |   h2   |
        |        |                                      |        |
        |10.0.0.1|                                      |10.0.0.2|
        |        |                                      |        |
        | h1-eth0| -----------------------------------  | h2-eth0|
        +---|----+                                      +---|----+
            |                                               |
            |                                               |
         eBPF:                                           eBPF:
         - edt_delay_packet.o                           - edt_delay_packet.o
         - xdp_drop_packet.o                            - xdp_drop_packet.o
```

```bash
.
├── README.md
├── ebpf-emu-in-mn
│   ├── h1
│   │   ├── edt_delay_packet.c                         ---- eBPF delay program on h1
│   │   └── xdp_drop_packet.c                          ---- eBPF loss program on h1
│   ├── h2
│   │   ├── edt_delay_packet.c                         ---- eBPF delay program on h2
│   │   └── xdp_drop_packet.c                          ---- eBPF loss program on h2
│   ├── mininet-2hop-emulate.py                        ---- main Mininet script
│   └── update_map_value.py                            ---- script for update eBPF maps
└── traces
    ├── LEO_downlink_delay-000001-12h.txt              ---- downlink delay trace (deploy on h2)
    ├── LEO_downlink_loss-000001-12h.txt               ---- downlink loss trace (deploy on h1)
    ├── LEO_uplink_delay-000001-12h.txt                ---- uplink delay trace (deploy on h1)
    ├── LEO_uplink_loss-000001-12h.txt                 ---- uplink loss trace (deploy on h2)
    └── make_trace_file.py                             ---- make traces from irtt json logs
```

## Step 1: Install necessary tools for eBPF
```bash
sudo apt update && sudo apt upgrade
sudo apt install linux-tools-common linux-tools-generic linux-tools-$(uname -r)
```

## Step 2: Prepare trace files from irtt measurement data

For convenience, in the `traces` folder we have included a set of ready-to-use uplink/downlink delay and loss traces, which are 10000-long segments of a 12-hour `irtt` measurement of a Starlink testbed (with interval 10ms). 

```
LEO_uplink_delay-000001-12h.txt			---- delay_map_1
LEO_downlink_delay-000001-12h.txt		---- delay_map_2
LEO_uplink_loss-000001-12h.txt			---- loss_map_1
LEO_downlink_loss-000001-12h.txt		---- loss_map_2
```

For more `irtt` dataset, you may access <https://github.com/clarkzjw/LENS>. A `make_trace_file.py` is included to help process the `irtt` json logs to the desired formats as those in `traces`. The readers are encouraged to read the script details.

## Step 3: Run Mininet script to create topology and deploy the eBPF programs
```bash
cd ebpf-emu-in-mn
```
The eBPF programs to be deployed are in the `h1` and `h2` folders. To proceed, first ensure that the `TRACE_LEN` macro of the programs `{h1,h2}/edt_delay_packet.c`, `{h1,h2}/xdp_drop_packet.c` are equal to the length of the corresponding traces. For the provided traces, the lengths are all 10000. 

After that, run

```bash
sudo python3 mininet-2hop-emulate.py
```
The script creates the two-node topology, and invokes commands on the hosts to compile and deploy the eBPF programs.

Run the following commands in either host's xterm to check whether the eBPF programs are deployed properly.

```
xterm h1
```

```bash
bpftool map show
```

If properly deployed, the following information should be seen

```bash
6: array name delay_map_1 flags 0x0
	key 4B value 4B max_entries 10000 memlock 80320B
	btf_id 109
10: array name loss_map_1 flags 0x0
	key 4B value 4B max_entries 10000 memlock 80320B
	btf_id 117
14: array name delay_map_2 flags 0x0
	key 4B value 4B max_entries 10000 memlock 80320B
	btf_id 123
18: array name loss_map_2 flags 0x0
	key 4B value 4B max_entries 10000 memlock 80320B
	btf_id 129
```


## Step 4: Update eBPF maps using the traces

As defined in the eBPF programs, the `delay_map_1` and `delay_map_2` are the map names corresponding to the uplink and downlink delay, respectively, and `loss_map_1` and `loss_map_2` are the map names corresponding to the downlink and uplink losses, respectively. 

We provide a `update_map_value.py` to update the maps based on the traces. To update the maps on `h1`, run the following commands in `h1`'s xterm (replace `YOUR_PATH_TO` accordingly)

```bash
sudo python3 update_map_value.py --keyword delay_map_1 --file_path /YOUR_PATH_TO/LEO_uplink_delay-000001-12h.txt
sudo python3 update_map_value.py --keyword loss_map_1 --file_path /YOUR_PATH_TO/LEO_downlink_loss-000001-12h.txt
```

Similarly, run the following to update `h2`'s maps in `h2`'s xterm

```bash
sudo python3 update_map_value.py --keyword delay_map_2 --file_path /YOUR_PATH_TO/LEO_downlink_delay-000001-12h.txt
sudo python3 update_map_value.py --keyword loss_map_2 --file_path /YOUR_PATH_TO/LEO_uplink_loss-000001-12h.txt
```

**The map updating takes time.** For example, updating 10000 data points may take a few seconds.


# Test the emulated link
After the emulation environment is configured, you may run `irtt` in Mininet to verify the emulated link. In `h2`'s xterm, run

```bash
irtt server -i 0
```

and then in `h1`'s xterm

```bash
irtt client -i 10ms -d 10s 10.0.0.2
```

The output would be like the following, which is almost a replay of the original delay and loss traces.

```
                         Min     Mean   Median      Max  Stddev
                         ---     ----   ------      ---  ------
                RTT  24.38ms  65.21ms  65.6ms   194ms    9.03ms
         send delay  12.05ms  33.24ms  33.09ms  103ms    5.37ms
      receive delay  11.54ms  31.98ms  32.23ms  90.98ms  5.17ms
                                                               
      IPDV (jitter)   17.3µs   3.32ms   2.24ms  139.9ms  5.59ms
          send IPDV   10.7µs   2.95ms   2.21ms  61.75ms  4.02ms
       receive IPDV   211ns   1.36ms    436µs   78.16ms  4.56ms
                                                               
     send call time   9.66µs   26.5µs            255µs   15.8µs
        timer error   472ns    259µs             1.28ms   172µs
  server proc. time   578s     7.35µs            55µs    4.34µs

                duration: 10.6s (wait 581.9ms)
   packets sent/received: 998/994 (0.40% loss)
 server packets received: 994/998 (0.40%/0.00% loss up/down)
late (out-of-order) pkts: 23(2.31%)
     bytes sent/received: 59880/59640
       send/receive rate: 48.0 Kbps / 47.9 Kbps
           packet length: 60 bytes
             timer stats: 2/1000 (0.20%) missed, 2.59% error

```

Note that the trace corresponds to 1000 packets, but the output of `irtt` over the emulated link would only show 998. The "missing" 2 are the handshake packets of `irtt`.

**ATTENTION**：Please note that, in the eBPF programs, we have used `FILTER_PORT` to only emulate delay and loss for a selected flow (so as not to affect other traffic). For `irtt`, the port is 2112. If you would like to test applications other than `irtt`, you need to change `FILTER_PORT` or define other flow filters accordingly before deploying the eBPF programs.

# Paper Citation
For more details about the method, please refer to

<blockquote>
    W. Tian, Y. Li, J. Zhao, S. Wu and J. Pan, "An eBPF-Based Trace-Driven Emulation Method for Satellite Networks", IEEE Networking Letters, 2024, Accepted. (Preprint of the submitted: https://arxiv.org/abs/2408.15581)
</blockquote>

If you find the method useful, please kindly cite the paper in your related works.
