# 100-window Qwen subset experiment

This is a deterministic 100-window Qwen subset experiment, not a 760-window full-dataset evaluation. BatteryData has no explicit fault labels; LOW/MEDIUM/HIGH are diagnostic anomaly severity only.

## Scope

- Available 10-file evaluation windows: 760
- Qwen subset windows: 100
- Unique selected identities: 100
- Same identities in both Qwen modes: True
- Model load time: 2.840 seconds

## Measured mode results

| Mode | AI calls | DDP calls | DDP retention | Total inference | Average inference | JSON success/failure | LOW/MEDIUM/HIGH |
|---|---:|---:|---:|---:|---:|---:|---:|
| Qwen Always-On | 100 | 100 | 8.0000% | 3886.250 s | 38.863 s | 99/1 | 99/0/0 |
| Qwen Event-Triggered | 60 | 60 | 5.8667% | 694.863 s | 11.581 s | 58/2 | 58/0/0 |

Calls avoided by event-triggered mode: 40 (40.00%).
