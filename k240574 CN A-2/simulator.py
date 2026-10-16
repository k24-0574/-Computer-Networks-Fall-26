# TASK 3: GBN and SR over a simulated unreliable channel
# Scenario link: R = 2 Mbps, RTT = 500 ms, L = 1000 bytes

#Sample command: python simulator.py --protocol gbn --packets 10 --window 4 --k 3 --loss 0.1

import argparse #to get arguments from command
import heapq # for priority queue
import random

L_BITS = 1000 * 8           # packet size
RATE = 2_000_000            # 2 Mbps
RTT = 0.5                   # 500 ms
TX = L_BITS / RATE          # transmission time
ONE_WAY = RTT / 2           # propagation delay of one way
SEED = 574                  # 24k-0574

def checksum(data: bytes) -> int:
    # 16-bit one's complement checksum
    if len(data) % 2:
        data += b"\x00" # odd
    total = 0
    for i in range(0, len(data), 2): # 16 bit word (2 byte)
        total += (data[i] << 8) + data[i + 1]
        total = (total & 0xFFFF) + (total >> 16) #keep lower but and add carry back
    return ~total & 0xFFFF # flip bits and return


def data_cks(seq, payload): # check seq num and payload
    return checksum(seq.to_bytes(2, "big") + payload)


def ack_cks(n): # check the ACKs
    return checksum(n.to_bytes(2, "big")) # turn ack into 2 bytes


class Sim:
    def __init__(self, a):  # a = (packets, window, loss, ...)
        self.a = a 
        self.M = 2 ** a.k # sqn num spack = 2^k
        self.rng = random.Random(a.seed)
        self.q, self.cnt = [], 0    # counter for events
        self.now = 0.0      # simulation clock
        self.link_free = 0.0    # time finished sending prev packet
        self.sent = self.retx = self.acks_sent = 0  #counters
        self.delivered = [] #delivered to application
        self.finish = None  # time at eveything ACKed
        self.data = [f"MSG-{i}".encode() for i in range(a.packets)] # the messages e.g. MSG-0

    def log(self, msg):
        if not self.a.quiet:    # for task 3 (for task 4 quite = true so no logging)
            print(f"[{self.now:8.3f}s] {msg}") # 8 +  3 d.p.

    def push(self, t, kind, payload):
        heapq.heappush(self.q, (t, self.cnt, kind, payload))
        self.cnt += 1

    # unreliable channel (for packets and ACKs)
    def channel(self, pkt, depart, to):
        r, a = self.rng, self.a
        name = f"{pkt[0]} {pkt[1]}"  # e.g. "DATA 3" or "ACK 2", used for logging
        if r.random() < a.loss: # loss
            self.log(f"CHANNEL  LOSS    {name}")
            return
        if r.random() < a.corrupt: #corrupt
            if pkt[0] == "DATA":
                pkt = ("DATA", pkt[1], bytes([pkt[2][0] ^ 0xFF]) + pkt[2][1:], pkt[3]) #first payload byte is flipped/XOR with ^ 0xFF,  old checksum pkt[3] is kept
            else:
                pkt = ("ACK", pkt[1] ^ 1, pkt[2]) # number is changed with ^ 1, old checksum pkt[2] is kept
            self.log(f"CHANNEL  CORRUPT {name}")
        d = ONE_WAY 
        if r.random() < a.delay:
            extra = r.uniform(0.05, 0.3) 
            d += extra # add extra delay
            self.log(f"CHANNEL  DELAY   {name} (+{extra:.3f}s)")
        self.push(depart + d, to, pkt) # schedule arrival

    def send_data(self, idx, retx):# idx =  pkt num, retx is retransmission
        seq = idx % self.M # wraparound seq no
        self.link_free = max(self.link_free, self.now) + TX # when will transmission complete
        self.sent += 1
        if retx: 
            self.retx += 1
        self.log(f"SENDER   {'RETRANSMIT' if retx else 'SEND'} pkt {seq} (#{idx})")
        pkt = ("DATA", seq, self.data[idx], data_cks(seq, self.data[idx]))
        self.channel(pkt, self.link_free, "to_receiver")

    def send_ack(self, n):
        self.acks_sent += 1
        self.log(f"RECEIVER SEND    ACK {n}")
        self.channel(("ACK", n, ack_cks(n)), self.now, "to_sender")

    def deliver(self, idx): # to application
        self.delivered.append(self.data[idx])
        self.log(f"RECEIVER DELIVER pkt #{idx} to application")

    def run(self):
        self.start()
        while self.q and self.finish is None and self.now < 1e6: #queue not empty, transfer not complete, clocl < 1e5 seconds (for safety)
            t, _, kind, p = heapq.heappop(self.q) # priority queue for earliest event
            self.now = t 
            if kind == "to_receiver":
                if p[3] != data_cks(p[1], p[2]): #check data
                    self.log(f"RECEIVER RECV    pkt {p[1]} CORRUPTED (checksum fail)")
                    self.rcv_corrupt()
                else:
                    self.log(f"RECEIVER RECV    pkt {p[1]}")
                    self.rcv_data(p[1])
            elif kind == "to_sender":
                if p[2] != ack_cks(p[1]): #check ACK
                    self.log(f"SENDER   RECV    ACK corrupted, ignored")
                else:
                    self.log(f"SENDER   RECV    ACK {p[1]}")
                    self.rcv_ack(p[1])
            else:
                self.on_timer(p)
        return self.stats()

    def stats(self):
        ok = self.delivered == self.data #checks delivered = sent
        t = self.finish if self.finish else self.now # t is the finish time ( = self.now if run ended without finishing)
        return dict(protocol=self.a.protocol.upper(), transmitted=self.sent,
                    retransmissions=self.retx, delivered=len(self.delivered),
                    correct_in_order=ok, time=t,
                    throughput=len(self.delivered) * L_BITS / t if t else 0)


class GBN(Sim): # inheret from Sim
    def __init__(self, a):
        super().__init__(a) #run sim setup
        self.base = self.nxt = self.expected = 0
        self.tver = 0

    def start(self):
        self.fill()

    def start_timer(self): # timer only for oldest unACKed pkt
        self.tver += 1
        self.push(self.now + self.a.timeout, "timer", self.tver)

    def stop_timer(self): 
        self.tver += 1 #next

    def fill(self):
        while self.nxt < self.a.packets and self.nxt < self.base + self.a.window: #send pkts while still space in window
            self.send_data(self.nxt, False) #new packet
            if self.base == self.nxt: #timer ony when it is the 1st packet of window
                self.start_timer()
            self.nxt += 1 #next seq num
            self.log(f"         window: base={self.base % self.M} "
                     f"nextseqnum={self.nxt % self.M}")

    def on_timer(self, ver):
        if ver != self.tver:
            return
        self.log(f"SENDER   TIMEOUT (base={self.base % self.M}) -> go back, resend "
                 f"{self.base % self.M}..{(self.nxt - 1) % self.M}")
        self.start_timer() #restart timer
        for i in range(self.base, self.nxt): #resend -> Go Back N
            self.send_data(i, True)

    def rcv_ack(self, n):
        for i in range(self.base, self.nxt):
            if i % self.M == n:
                self.base = i + 1 # cumulative ACK
                self.log(f"SENDER   cumulative ACK {n}: base={self.base % self.M}")
                if self.base == self.nxt: #nothing left to restransmit
                    self.stop_timer()
                else:
                    self.start_timer()
                if self.base == self.a.packets: # every thing ACKed
                    self.finish = self.now
                else:
                    self.fill() #send more packets
                return
        self.log("SENDER   duplicate/old ACK ignored")

    def rcv_corrupt(self): # not delivered
        if self.expected > 0: # if there is a prev packet
            self.send_ack((self.expected - 1) % self.M) #repeated ACK

    def rcv_data(self, seq):
        if seq == self.expected % self.M: # if in order
            self.deliver(self.expected)
            self.send_ack(seq)
            self.expected += 1
        else:
            self.log(f"RECEIVER DISCARD pkt {seq} (out of order, expectedseqnum="
                     f"{self.expected % self.M})")
            if self.expected > 0:
                self.send_ack((self.expected - 1) % self.M)


class SR(Sim):
    def __init__(self, a):
        super().__init__(a) 
        self.sbase = self.nxt = 0 # sbase = oldest packet not ACKed
        self.acked = set()
        self.tv = {} # timer version for packets (Dictionary) ->one timer per packet
        self.rbase = 0 # start of reciever window
        self.buf = {} #buffer

    def start(self):
        self.fill()

    def start_timer(self, i):
        self.tv[i] = self.tv.get(i, 0) + 1 # read curr ver, if none, default = 0
        self.push(self.now + self.a.timeout, "timer", (i, self.tv[i])) #timeout 

    def fill(self): #send new packets
        while self.nxt < self.a.packets and self.nxt < self.sbase + self.a.window:
            self.send_data(self.nxt, False)
            self.start_timer(self.nxt)
            self.nxt += 1
            self.log(f"         sender window: [{self.sbase % self.M}.."
                     f"{(self.sbase + self.a.window - 1) % self.M}]")

    def on_timer(self, p):
        i, ver = p
        if self.tv.get(i) != ver or i in self.acked: #ignore if outdated ver or ACKed
            return
        self.log(f"SENDER   TIMEOUT pkt {i % self.M} -> resend only this packet")
        self.send_data(i, True)
        self.start_timer(i)

    def rcv_ack(self, n):
        for i in range(self.sbase, min(self.sbase + self.a.window, self.nxt)): #sender window
            if i % self.M == n: #abs index
                if i in self.acked:
                    self.log("SENDER   duplicate ACK ignored")
                    return
                self.acked.add(i)
                self.tv[i] += 1  # cancel timer
                self.log(f"SENDER   individual ACK {n} marked")
                while self.sbase in self.acked: #window moves forwrd
                    self.sbase += 1
                self.log(f"         send_base={self.sbase % self.M}")
                if self.sbase == self.a.packets: #all packets ACKed
                    self.finish = self.now
                else:
                    self.fill() #send new packets
                return
        self.log("SENDER   old ACK ignored")

    def rcv_corrupt(self):
        pass  # corrupted packet is dropped

    def rcv_data(self, seq):
        N = self.a.window # reciever window
        for d in range(N):
            i = self.rbase + d # abs index
            if i < self.a.packets and i % self.M == seq:
                self.send_ack(seq) # individual ACK sent
                if i not in self.buf: 
                    self.buf[i] = True
                    if i != self.rbase: # arrived early/out of order
                        self.log(f"RECEIVER BUFFER  pkt {seq} (out of order, "
                                 f"rcv_base={self.rbase % self.M})")
                while self.rbase in self.buf:   #deliver while consecutive buffered from rbase
                    self.deliver(self.rbase)
                    del self.buf[self.rbase]
                    self.rbase += 1
                self.log(f"         receiver window: rcv_base={self.rbase % self.M}")
                return
        for d in range(1, N + 1): 
            if (self.rbase - d) % self.M == seq and self.rbase - d >= 0:    #already delivered (ACK lost)
                self.log(f"RECEIVER old pkt {seq} already delivered, re-ACK")
                self.send_ack(seq) # again ACK
                return
        self.log(f"RECEIVER pkt {seq} outside window, ignored")


def run_sim(protocol, packets, window, k, loss, corrupt, delay, timeout, seed, quiet=False):
    a = argparse.Namespace(protocol=protocol, packets=packets, window=window, k=k,
                           loss=loss, corrupt=corrupt, delay=delay, timeout=timeout,
                           seed=seed, quiet=quiet)
    limit = 2 ** k - 1 if protocol == "gbn" else 2 ** (k - 1)
    if window > limit:
        raise ValueError(f"{protocol.upper()} with k={k} needs window <= {limit}")
    return (GBN if protocol == "gbn" else SR)(a).run()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--protocol", choices=["gbn", "sr"], default="gbn")
    p.add_argument("--packets", type=int, default=10)
    p.add_argument("--window", type=int, default=4)
    p.add_argument("--k", type=int, default=3)
    p.add_argument("--loss", type=float, default=0.0)
    p.add_argument("--corrupt", type=float, default=0.0)
    p.add_argument("--delay", type=float, default=0.0)
    p.add_argument("--timeout", type=float, default=1.0)
    p.add_argument("--quiet", action="store_true")
    a = p.parse_args()
    s = run_sim(a.protocol, a.packets, a.window, a.k, a.loss, a.corrupt, a.delay,
                a.timeout, SEED, a.quiet)
    print("\n--- SUMMARY ---")
    for key, v in s.items():
        print(f"{key}: {v:.4f}" if isinstance(v, float) else f"{key}: {v}")
