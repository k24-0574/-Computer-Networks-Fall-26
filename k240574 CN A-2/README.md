# Computer Network - CS3001 Assignment-II

## Files
- `simulator.py` : GBN and SR sender/receiver with a simulated unreliable channel (Task 3)
- `experiments.py` : runs scenarios A, B, C for both protocols, prints the results table and saves the graph (Task 4)

## Requirements
- Python 3.12 or later
- `matplotlib` (only for `experiments.py`): `pip install matplotlib`

## How to run

### 1. Simulator (Task 3)
```
python simulator.py --protocol gbn --packets 10 --window 4 --k 3 --loss 0.1
```

### 2. Experiments (Task 4)
```
python experiments.py
```
Runs both protocols with 200 packets, N = 4, k = 3 under scenarios A, B and C. It prints the results table and saves `results.csv` and `gbn_vs_sr.png`.

## Parameters (`simulator.py`)
| Parameter | Meaning | Default |
|---|---|---|
| `--protocol` | `gbn` or `sr` | gbn |
| `--packets` | Number of packets | 10 |
| `--window` | Window size N (GBN: N <= 2^k - 1, SR: N <= 2^(k-1)) | 4 |
| `--k` | Sequence-number bits, numbers wrap modulo 2^k | 3 |
| `--loss` | Loss probability (packets and ACKs) | 0.0 |
| `--corrupt` | Corruption probability (packets and ACKs, detected by checksum) | 0.0 |
| `--delay` | Delay probability (packets and ACKs) | 0.0 |
| `--timeout` | Retransmission timeout in seconds | 1.0 |
| `--quiet` | Hide the log lines | off |


## Sample command
```
python simulator.py --protocol gbn --packets 10 --window 4 --k 3 --loss 0.1
```