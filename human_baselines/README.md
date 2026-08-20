# Human baseline scripts

Hand-written grep/Python reference scripts representing a typical sysadmin
approach to each query. We use them as the comparison point for LLM-generated
filters in the `human-baseline` experiment.

## Layout

```
human_baselines/
  audit_simple/      9 .sh + 3 .py
  audit_complex/     8 .py
  cron_simple/       9 .sh + 3 .py
  cron_complex/      8 .py
  puppet_simple/     9 .sh + 3 .py
  puppet_complex/    8 .py
  sshd_simple/       9 .sh + 3 .py
  sshd_complex/      8 .py
  dhcp_simple/       22 .sh + 10 .py
  dhcp_complex/      21 .py
```

## Running a single script

```bash
bash human_baselines/audit_simple/audit_query_1.sh data/logs/audit
python3 human_baselines/dhcp_complex/multiline_3.py data/logs/dhcp
```

## Running the full baseline

```bash
python3 experiments.py --experiment human-baseline \
    --datasets dhcp_simple dhcp_complex audit_simple audit_complex \
               puppet_simple puppet_complex sshd_simple sshd_complex \
               cron_simple cron_complex
```

The runner writes one report per dataset under
`eval/experiments/human-baseline/<timestamp>/`.
