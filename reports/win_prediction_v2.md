# Win Prediction v2 Report

- train games: 431, val: 91, test: 91
- train samples: 103440, val: 21840, test: 21840
- train positive rate: 0.500

## Constant baseline (P=0.500)
- acc=0.500  brier=0.2500  logloss=0.6931  auc=0.500

## Logistic Regression (calibrated)
- acc=0.717  auc=0.818  prauc=0.830  brier=0.1756  logloss=0.5091  ece=0.0532  bacc=0.717  T=1.30

## MLP Win Predictor (3 seeds, calibrated)
- acc: mean=0.6845  std=0.0024
- auc: mean=0.7804  std=0.0036
- prauc: mean=0.7887  std=0.0039
- brier: mean=0.1932  std=0.0045
- logloss: mean=0.5611  std=0.0137
- ece: mean=0.0654  std=0.0081
- bacc: mean=0.6845  std=0.0024
- T: mean=2.8667  std=1.0850

## Time-segmented evaluation (test)
| window | n | acc | auc | brier | ece |
|---|---|---|---|---|---|
| 0-60s | 3114 | 0.613 | 0.675 | 0.2243 | 0.0361 |
| 60-120s | 3114 | 0.636 | 0.724 | 0.2136 | 0.0756 |
| 120-180s | 3112 | 0.664 | 0.762 | 0.1988 | 0.0634 |
| 180-240s | 3292 | 0.673 | 0.778 | 0.1917 | 0.0742 |
| 240-300s | 3114 | 0.727 | 0.832 | 0.1672 | 0.0501 |
| 300-9999s | 6094 | 0.743 | 0.846 | 0.1620 | 0.0573 |

## Team-held-out test (unseen schools)
- unseen schools: 19  samples: 50640
- acc=0.802  auc=0.896  brier=0.1342  ece=0.0490
