# TASK 4: run GBN and SR for scenarios A, B, C (200 packets, N=4, k=3)

import matplotlib
matplotlib.use("Agg") # to draw into an image file, do not open a window
import matplotlib.pyplot as plt
from simulator import run_sim

SEED = 574  #24k-0574
SCEN = {"A: Reliable": (0.0, 0.0, 0.0),
        "B: Loss 0.10": (0.10, 0.0, 0.0),
        "C: Mixed": (0.05, 0.05, 0.10)}

rows = []
for name, (loss, cor, dly) in SCEN.items(): #run for each scenario for GBN and SR
    for proto in ("gbn", "sr"):
        s = run_sim(proto, 200, 4, 3, loss, cor, dly, 1.0, SEED, quiet=True) #quite so np log file
        rows.append((name, s))

print(f"{'Scenario':<14}{'Proto':<6}{'Transmitted':>12}{'Retrans':>9}"
      f"{'Delivered':>10}{'Time(s)':>9}{'Thput(kbps)':>12}{'Correct':>9}")
for name, s in rows:
    print(f"{name:<14}{s['protocol']:<6}{s['transmitted']:>12}{s['retransmissions']:>9}"
          f"{s['delivered']:>10}{s['time']:>9.2f}{s['throughput']/1000:>12.2f}"
          f"{str(s['correct_in_order']):>9}")

with open("results.csv", "w") as f:
    f.write("scenario,protocol,transmitted,retransmissions,delivered,time_s,throughput_bps\n")
    for name, s in rows:
        f.write(f"{name},{s['protocol']},{s['transmitted']},{s['retransmissions']},"
                f"{s['delivered']},{s['time']:.3f},{s['throughput']:.1f}\n")

names = list(SCEN)
fig, ax = plt.subplots(1, 2, figsize=(11, 4))
w = 0.35
for j, (metric, title, ylab) in enumerate([("retransmissions", "Retransmissions", "Packets"),
                                           ("time", "Execution time", "Seconds")]):
    for off, proto in ((-w / 2, "GBN"), (w / 2, "SR")):
        vals = [s[metric] for n, s in rows if s["protocol"] == proto]
        ax[j].bar([i + off for i in range(3)], vals, w, label=proto)
    ax[j].set_xticks(range(3))
    ax[j].set_xticklabels(names)
    ax[j].set_title(f"GBN vs SR: {title}")
    ax[j].set_ylabel(ylab)
    ax[j].legend()
plt.tight_layout()
plt.savefig("gbn_vs_sr.png", dpi=150)

print("Saved results.csv and gbn_vs_sr.png")