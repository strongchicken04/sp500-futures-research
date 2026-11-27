#!/bin/bash
# Stage 4.6 runner (adapted from run_s45.sh): one MODE of the Stage 3 panel + Stage 4 modules in QC; appends runtime statistics + log lines
# (aggregates only) to results/xup_s4_<mode>_raw.txt with a validation verdict and the run identifiers.
# Usage: run_s46.sh MODE [label]    MODE in S46AUDIT S46MAIN S46ROBUST S46SHADOW
# The committed Stage 3 panel file is NOT modified: a temporary copy gets MODE and the Stage 4 attachments.
MODE=$1; LABEL=${2:-v1}
cd "$(dirname "$0")/../.."
SRC=strategy/quantconnect/inqc/xup_s3_panel_inqc.py
TMP=$(mktemp -d)/main_s46.py
sed "s/^MODE = \"AUDIT\"/MODE = \"$MODE\"/" $SRC > $TMP
cat >> $TMP <<'EOF'

# ---- Stage 4 attachments (added by run_s4.sh; the Stage 3 methods stay unchanged, _security is wrapped) ----
from xup_s4_core import S4Core
from xup_s4_modes_a import S4ModesA
from xup_s4_modes_b import S4ModesB
from xup_s4_modes_c import S4ModesC
from xup_s4_modes_d import S4ModesD
from xup_s4_modes_e import S4ModesE
XupS3Panel._security_s3 = XupS3Panel._security
for _M in (S4Core, S4ModesA, S4ModesB, S4ModesC, S4ModesD, S4ModesE):
    for _n, _f in list(vars(_M).items()):
        if not _n.startswith("__"):
            setattr(XupS3Panel, _n, _f)
from xup_s45_core import S45Core
from xup_s45_modes_a import S45ModesA
from xup_s45_modes_b import S45ModesB
from xup_s45_modes_c import S45ModesC
from xup_s45_modes_d import S45ModesD
XupS3Panel._security_s4 = XupS3Panel._security
for _M in (S45Core, S45ModesA, S45ModesB, S45ModesC, S45ModesD):
    for _n, _f in list(vars(_M).items()):
        if not _n.startswith("__"):
            setattr(XupS3Panel, _n, _f)
from xup_s46_core import S46Core
from xup_s46_modes import S46Modes
XupS3Panel._security_s45 = XupS3Panel._security
for _M in (S46Core, S46Modes):
    for _n, _f in list(vars(_M).items()):
        if not _n.startswith("__"):
            setattr(XupS3Panel, _n, _f)
EOF
X=$(ls strategy/quantconnect/inqc/xup_ic_*.py strategy/quantconnect/inqc/xup_s3_const.py strategy/quantconnect/inqc/xup_s3_modes_*.py strategy/quantconnect/inqc/xup_s4_*.py strategy/quantconnect/inqc/xup_s45_*.py strategy/quantconnect/inqc/xup_s46_*.py | tr '\n' ',' | sed 's/,$//')
OUT=results/xup_s46_$(echo ${MODE#S46} | tr A-Z a-z)_raw.txt
LOG=/tmp/s46_${MODE}_log.txt
for f in $(echo $X | tr ',' ' ') $TMP; do
  n=$(wc -c < $f); if [ $n -gt 32000 ]; then echo "FILE TOO LARGE $f $n"; exit 1; fi
done
for i in $(seq 1 90); do
  QC_EXTRA_FILES=$X python3 strategy/quantconnect/deploy_long.py MSXB_1792352605 $TMP > $LOG 2>&1
  if grep -qi "no spare nodes" $LOG; then sleep 60; continue; fi
  break
done
python3 strategy/quantconnect/s4_collect.py "$MODE" "$LABEL" "$LOG" >> $OUT
git checkout -- qc_result_MSXB_1792352605.json 2>/dev/null
grep "### xup s4 $MODE $LABEL" $OUT | tail -1
