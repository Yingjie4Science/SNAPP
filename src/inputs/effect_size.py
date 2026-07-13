#!/usr/bin/env python3
"""
Convert a published ODDS RATIO to the RISK RATIO the InVEST model expects.

Why this exists
    The default exposure-response comes from Liu et al. (2023), Environmental
    Research 231:116303 — a meta-analysis reporting a pooled ODDS RATIO of
    0.931 (95% CI 0.887-0.977) per +0.1 NDVI for depression. InVEST's
    `effect_size` is applied as a RISK RATIO (RR): the model computes
    preventable_cases = (1 - exp(ln(effect_size)*10*dNDVI)) * baseline_cases,
    i.e. it treats effect_size as a per-0.1-NDVI multiplier on RISK. Because
    depression is common (~20% prevalence), an OR sits further from 1 than the
    true RR, so using the OR directly OVERSTATES preventable cases.

Conversion (Zhang & Yu 1998, JAMA 280:1690)
    RR = OR / (1 - p0 + p0 * OR)
    where p0 = baseline risk in the reference (unexposed / least-green) group.
    We approximate p0 by the population prevalence of depression (a standard,
    slightly conservative simplification). RR is insensitive to p0 across the
    plausible 0.15-0.25 range (central RR ~0.941-0.947).

USAGE
    python src/inputs/effect_size.py                 # convert config OR at p0
    python src/inputs/effect_size.py --or 0.931 --p0 0.20
    python src/inputs/effect_size.py --or 0.931 0.887 0.977 --p0 0.20
"""

import argparse
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]


def or_to_rr(odds_ratio: float, p0: float) -> float:
    """Zhang & Yu (1998) OR->RR conversion at baseline risk p0 (in 0-1)."""
    if not (0.0 < p0 < 1.0):
        raise ValueError(f"p0 must be in (0,1); got {p0}")
    return odds_ratio / (1.0 - p0 + p0 * odds_ratio)


def _load_cfg():
    try:
        import yaml
        p = BASE_DIR / "config.yaml"
        if p.exists():
            return yaml.safe_load(p.read_text()) or {}
    except Exception:
        pass
    return {}


def main():
    cfg = _load_cfg().get("model", {})
    ap = argparse.ArgumentParser(description="Convert odds ratio(s) to risk ratio(s).")
    ap.add_argument("--or", dest="ors", type=float, nargs="*",
                    help="Odds ratio(s). Default: config effect_size_or[/_low/_high].")
    ap.add_argument("--p0", type=float,
                    default=float(cfg.get("baseline_risk_p0", 0.20)),
                    help="Baseline risk (prevalence) for the conversion. Default from "
                         "config baseline_risk_p0, else 0.20.")
    ap.add_argument("--p0-sweep", nargs="*", type=float,
                    help="Show RR (and %% change in cases) across a p0 grid. Bare flag "
                         "uses 0.10 0.15 0.20 0.25 0.30; or pass your own values.")
    cli = ap.parse_args()

    ors = cli.ors
    if not ors:
        ors = [cfg.get("effect_size_or", 0.931),
               cfg.get("effect_size_or_low", 0.887),
               cfg.get("effect_size_or_high", 0.977)]

    if cli.p0_sweep is not None:
        import math
        grid = cli.p0_sweep or [0.10, 0.15, 0.20, 0.25, 0.30]
        or_c = float(ors[0])
        ref = or_to_rr(or_c, cli.p0)
        print(f"p0 sensitivity for central OR {or_c:.3f} (ref p0={cli.p0}):")
        print(f"{'p0':>6}  {'RR':>8}  {'~% cases vs ref':>16}")
        for p in grid:
            rr = or_to_rr(or_c, p)
            # small-dNDVI regime: preventable cases ~ proportional to -ln(RR)
            pct = 100.0 * (math.log(rr) / math.log(ref) - 1.0)
            print(f"{p:6.2f}  {rr:8.4f}  {pct:+15.1f}%")
        return

    print(f"p0 = {cli.p0}")
    print(f"{'OR':>8}  {'RR':>8}")
    for o in ors:
        print(f"{o:8.3f}  {or_to_rr(float(o), cli.p0):8.4f}")


if __name__ == "__main__":
    main()
