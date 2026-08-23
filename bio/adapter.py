#!/usr/bin/env python3
"""Adapter skeleton for the bio arm. Runs today against the internal mock;
the CL1 simulator client drops into the same interface when installed.

The design principle is stated here so no reader can miss it: the neurons do
not speak. Every semantic element of the output text is authored by the
Decoder below. That authorship is the object of study, never a bug. The paired
NoiseSource exists so that the claim can be tested: if battery responses
produced from the culture and from matched noise are indistinguishable
downstream, the pipeline is measuring the adapter.

Interface to implement against the real SDK later:
    CL1SimSource / CL1LiveSource with the same .record(seconds) contract.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import random
import sys
import time

CHANNELS = 59          # planar array electrode count, per public CL1 specs
DT_MS = 1.0            # bin width for spike counts
REFRACTORY_MS = 2.0


@dataclasses.dataclass
class SpikeTrain:
    """Per-channel spike timestamps in milliseconds, plus provenance."""
    source: str
    seconds: float
    spikes: list[list[float]]

    def rates_hz(self) -> list[float]:
        return [len(ch) / self.seconds for ch in self.spikes]


class NoiseSource:
    """Spike-matched noise: Poisson per channel with refractory, rates taken
    from a reference recording so arms 3 and 4 are statistically paired."""

    def __init__(self, rates_hz: list[float], seed: int):
        assert len(rates_hz) == CHANNELS
        self.rates = rates_hz
        self.rng = random.Random(seed)

    def record(self, seconds: float) -> SpikeTrain:
        out = []
        for r in self.rates:
            t, ch = 0.0, []
            while True:
                if r <= 0:
                    break
                t += self.rng.expovariate(r) * 1000.0
                if ch and t - ch[-1] < REFRACTORY_MS:
                    t = ch[-1] + REFRACTORY_MS
                if t >= seconds * 1000.0:
                    break
                ch.append(t)
            out.append(ch)
        return SpikeTrain("noise", seconds, out)


class MockCultureSource:
    """Stand-in for the CL1 simulator client until it is installed. Produces
    bursty activity so the two arms are not trivially identical at the spike
    level; the point of the experiment is whether anything downstream can
    tell them apart through the same decoder."""

    def __init__(self, seed: int):
        self.rng = random.Random(seed)

    def record(self, seconds: float) -> SpikeTrain:
        out = []
        for _ in range(CHANNELS):
            ch, t = [], 0.0
            while t < seconds * 1000.0:
                t += self.rng.expovariate(0.5) * 1000.0     # burst onsets
                for k in range(self.rng.randint(2, 9)):      # burst
                    tk = t + k * (REFRACTORY_MS + self.rng.random() * 3)
                    if tk < seconds * 1000.0:
                        ch.append(tk)
            out.append(sorted(ch))
        return SpikeTrain("mock_culture", seconds, out)


def encode(item_id: str, text: str, run_salt: str) -> dict:
    """Item to stimulation pattern. Arbitrary by necessity. The mapping is
    salted per run: a stable item-to-pattern code would itself transmit item
    identity, so each run remaps. Within a run every arm still receives the
    same stimulus for the same item."""
    h = hashlib.sha256(f"{run_salt}:{item_id}:{text}".encode()).digest()
    return {"item": item_id,
            "channels": [h[i] % CHANNELS for i in range(8)],
            "pulses": [50 + h[8 + i] % 200 for i in range(8)]}


def decode(train: SpikeTrain) -> str:
    """Spikes to text. THIS FUNCTION IS THE LAST AND LARGEST HAND on the pen;
    encoder, serialization, prompt framing and any downstream narrator or
    observer also author. The decoder is deliberately item-blind: it never
    receives the item id, so no item identity can pass through the text it
    writes. It emits a fixed template parameterized only by spike statistics.
    An item-decodability test accompanies every run: a classifier trying to
    recover the item from these outputs must sit at chance."""
    r = train.rates_hz()
    mean = sum(r) / len(r)
    active = sum(1 for x in r if x > 0.5)
    return (f"Attivita' registrata su {active} canali su {CHANNELS}, "
            f"frequenza media {mean:.1f} Hz nella finestra di {train.seconds:.0f} s. "
            f"Nessun contenuto oltre queste statistiche e' presente nel segnale; "
            f"ogni ulteriore formulazione appartiene alla pipeline.")


def run(source, source_name: str, items_path: str, out_path: str) -> None:
    items = json.load(open(items_path, encoding="utf-8"))
    with open(out_path, "w", encoding="utf-8") as f:
        run_salt = hashlib.sha256(str(time.time()).encode()).hexdigest()[:12]
        for item_id, text in items:
            _ = encode(item_id, text, run_salt)  # stimulation would happen here
            train = source.record(seconds=10)
            resp = decode(train)                 # decoder never sees the item
            f.write(json.dumps({
                "item": item_id, "condition": "A", "substrate": source_name,
                "quant": "", "response": resp,
                "rates_hz": [round(x, 2) for x in train.rates_hz()],
            }, ensure_ascii=False) + "\n")
            time.sleep(0)


if __name__ == "__main__":
    # usage: python3 adapter.py items.json
    items_path = sys.argv[1] if len(sys.argv) > 1 else "items.json"
    culture = MockCultureSource(seed=7)
    ref = culture.record(seconds=10)            # pair the noise to the culture
    noise = NoiseSource(ref.rates_hz(), seed=13)
    run(culture, "cl1_mock", items_path, "braccio_cl1_mock.jsonl")
    run(noise, "spike_noise", items_path, "braccio_noise.jsonl")
    print("scritti braccio_cl1_mock.jsonl e braccio_noise.jsonl")
