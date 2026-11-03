# Transport model identity certificate

`certificate.json` passes all four cases. This is model-reuse evidence for the
controlled-ISP `FULL=1`, `STYLE=0` PAXI fixtures. It is not a new simulation run,
style-pixel validation, physical DDR validation or board acceptance.

The original PASS reports, logs, exact testbenches, compiled `sim.vvp` files,
compile commands and all old source contents were copied before the DSP style
patch into `validation/pre_dsp_transport_models`. Its manifest SHA-256 is:

```
40250b9f432e6ba8bf8f9d2b969ff153bfa866f1560c705ddd07ef83d668f10c
```

The only permitted changed compiled input is:

```
user_source/hdl_source/isp/stylize_v5_96.v
old: 72a26a350f1c7089bd49503378c0d04ec3b92d7fd808563b13d548915b4009aa
new: 4ea577328c6af4a7696e2a3e2764b4fd961c85d2a149ba59acb6d7ab1a26d207
```

Every other compiled input, fixture, original report/log/binary, compiler and
runtime dependency remains hash-bound. The tool recompiles the original top and
arguments, changing only the `-o` output filename. All four original and newly
compiled models have `FULL=1`, `STYLE=0`, with no elaborated stylize/style-guide
module instance.

The comparison alpha-renames pointer-derived object-address labels by first
appearance, retaining their namespace and every array/concat index suffix.
It preserves quoted strings, file_names paths, opcodes, operands, constants,
events, delays and CRLF bytes. It does not sort, remove or rewrite instructions.
Any remaining textual difference rejects reuse. Negative self-checks demonstrate
that opcode, constant, delay, quoted text, single/double suffix and line-ending
mutations are rejected.

The first normalizer trial correctly refused unknown `o...` labels. Inspection
showed these are real `BUFZ` HiZ-drive object definitions and net references.
A later refusal exposed unrecognized `LS_<address>_0_0` / `_0_4` concat-label
suffixes. The retained diagnostic diff is in `normalizer_development`.
The final implementation recognizes those address-label formats, preserves all
functor text and numeric suffixes, and achieves exact text equality without
instruction or ordering exceptions.

## Exporter verification

Run this check before permitting the old reports to satisfy current-source
transport acceptance:

```powershell
python tools/verify_v16_transport_model_identity.py --check-certificate
```

Or import the same tool and call `check_certificate()`. That function rechecks
the current source hashes, snapshot and original report/log/binary hashes,
new binary hashes, runtime dependencies, exact compile arguments, absence of
style instances, normalizer guards, and exact normalized model text.

Final verifier SHA-256:

```
199bab47caf60c2b670c5eabd453587db155f341c5a08b1df88b78549422b906
```

Certificate SHA-256:

```
0b2ad96742aa12a61627dd090a905719df37f5bb0fc23a96cdf0dd650be37e58
```

The original test reports have not been edited or relabeled as fresh runs.
