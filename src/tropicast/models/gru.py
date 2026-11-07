"""GRU deep ensemble with heteroscedastic Gaussian outputs.

Input: track-history sequence (``SEQ_FEATURES`` per 6 h step) + static context
vector. Output per lead and target (dx, dy, dw): mean and log-variance. Loss:
Gaussian NLL, masked where targets are missing. Uncertainty: deep ensemble
(Lakshminarayanan et al., 2017) - total variance = mean aleatoric variance +
variance of member means. Raw spread is later re-calibrated by conformal
calibration on the validation set (see :mod:`tropicast.models.uncertainty`).
"""
from __future__ import annotations

import copy
import logging

import numpy as np
import torch
from torch import nn

from tropicast.datasets.samples import SampleSet

log = logging.getLogger(__name__)
TARGETS = ("dx", "dy", "dw")
STATIC = ["wind", "pres_filled", "pres_missing", "dist2land", "month_sin", "month_cos", "age_h", "is_as",
          "hist_len", "lat", "lon"]


class _Net(nn.Module):
    def __init__(self, n_seq: int, n_static: int, n_out: int, hidden: int, layers: int, dropout: float):
        super().__init__()
        self.gru = nn.GRU(n_seq, hidden, num_layers=layers, batch_first=True)
        self.head = nn.Sequential(
            nn.Linear(hidden + n_static, hidden), nn.GELU(), nn.Dropout(dropout),
            nn.Linear(hidden, 2 * n_out),
        )
        self.n_out = n_out

    def forward(self, seq, static):
        _, h = self.gru(seq)
        z = torch.cat([h[-1], static], dim=1)
        o = self.head(z)
        mu, logvar = o[:, : self.n_out], o[:, self.n_out:].clamp(-8, 8)
        return mu, logvar


class GRUEnsemble:
    name = "gru_ensemble"
    features = STATIC

    def __init__(self, hidden=64, layers=1, dropout=0.1, epochs=60, lr=2e-3, batch_size=128, ensemble=5,
                 patience=8, seed=42, static: list[str] | None = None, **_):
        self.hp = dict(hidden=hidden, layers=layers, dropout=dropout)
        self.static = list(static or STATIC)
        self.features = self.static
        self.epochs, self.lr, self.bs, self.k, self.patience, self.seed = epochs, lr, batch_size, ensemble, patience, seed
        self.members: list[_Net] = []
        self.norm: dict[str, np.ndarray] = {}
        self.leads: list[int] = []

    # ---- tensors -------------------------------------------------------
    def _arrays(self, s: SampleSet, fit_norm: bool = False):
        seq = s.seq.astype(np.float32)
        static = s.frame[self.static].to_numpy(np.float32)
        y = np.concatenate([s.frame[s.target_cols(t)].to_numpy(np.float32) for t in TARGETS], axis=1)
        if fit_norm:
            self.norm = {
                "seq_mu": seq.reshape(-1, seq.shape[-1]).mean(0), "seq_sd": seq.reshape(-1, seq.shape[-1]).std(0) + 1e-6,
                "st_mu": np.nanmean(static, 0), "st_sd": np.nanstd(static, 0) + 1e-6,
                "y_mu": np.nanmean(y, 0), "y_sd": np.nanstd(y, 0) + 1e-6,
            }
        n = self.norm
        seq = (seq - n["seq_mu"]) / n["seq_sd"]
        static = np.nan_to_num((static - n["st_mu"]) / n["st_sd"])
        mask = np.isfinite(y).astype(np.float32)
        y = np.nan_to_num((y - n["y_mu"]) / n["y_sd"])
        return torch.from_numpy(seq), torch.from_numpy(static), torch.from_numpy(y), torch.from_numpy(mask)

    @staticmethod
    def _nll(mu, logvar, y, m):
        l = 0.5 * (logvar + (y - mu) ** 2 / logvar.exp())
        return (l * m).sum() / m.sum().clamp(min=1)

    def fit(self, train: SampleSet, val: SampleSet | None = None) -> "GRUEnsemble":
        self.leads = list(train.leads)
        tr = self._arrays(train, fit_norm=True)
        va = self._arrays(val) if val is not None and len(val.frame) else None
        n_out = tr[2].shape[1]
        self.members = []
        for k in range(self.k):
            torch.manual_seed(self.seed + k)
            rng = np.random.default_rng(self.seed + k)
            net = _Net(tr[0].shape[-1], tr[1].shape[1], n_out, **self.hp)
            opt = torch.optim.AdamW(net.parameters(), lr=self.lr, weight_decay=1e-4)
            best, best_state, bad = np.inf, None, 0
            n = len(tr[0])
            for ep in range(self.epochs):
                net.train()
                for idx in np.array_split(rng.permutation(n), max(1, n // self.bs)):
                    mu, lv = net(tr[0][idx], tr[1][idx])
                    loss = self._nll(mu, lv, tr[2][idx], tr[3][idx])
                    opt.zero_grad()
                    loss.backward()
                    nn.utils.clip_grad_norm_(net.parameters(), 5.0)
                    opt.step()
                if va is None:
                    continue
                net.eval()
                with torch.no_grad():
                    vl = float(self._nll(*net(va[0], va[1]), va[2], va[3]))
                if vl < best - 1e-4:
                    best, best_state, bad = vl, copy.deepcopy(net.state_dict()), 0
                else:
                    bad += 1
                    if bad >= self.patience:
                        break
            if best_state is not None:
                net.load_state_dict(best_state)
            log.info("GRU member %d: best val NLL %.4f (epoch stop %d)", k, best, ep)
            net.eval()
            self.members.append(net)
        return self

    def predict(self, s: SampleSet, mc_members: bool = False):
        seq, static, _, _ = self._arrays(s)
        mus, vars_ = [], []
        with torch.no_grad():
            for net in self.members:
                mu, lv = net(seq, static)
                mus.append(mu.numpy())
                vars_.append(lv.exp().numpy())
        mus, vars_ = np.stack(mus), np.stack(vars_)
        sd = self.norm["y_sd"]
        mean = mus.mean(0) * sd + self.norm["y_mu"]
        var = (vars_.mean(0) + mus.var(0)) * sd ** 2
        L = len(self.leads)
        out = {t: mean[:, i * L:(i + 1) * L] for i, t in enumerate(TARGETS)}
        v = {t: var[:, i * L:(i + 1) * L] for i, t in enumerate(TARGETS)}
        out["track_sigma"] = np.sqrt((v["dx"] + v["dy"]) / 2)
        wsd = np.sqrt(v["dw"])
        out["dw_lo"], out["dw_hi"] = out["dw"] - 1.645 * wsd, out["dw"] + 1.645 * wsd
        if mc_members:
            out["members"] = mus * sd + self.norm["y_mu"]
        return out

    # ---- persistence ----------------------------------------------------
    def state(self) -> dict:
        return {"hp": self.hp, "leads": self.leads, "norm": self.norm, "k": self.k, "static": self.static,
                "members": [m.state_dict() for m in self.members],
                "dims": (self.members[0].gru.input_size, self.members[0].head[0].in_features - self.hp["hidden"],
                         self.members[0].n_out)}

    @classmethod
    def from_state(cls, st: dict) -> "GRUEnsemble":
        obj = cls(**st["hp"], ensemble=st["k"], static=st.get("static"))
        obj.leads, obj.norm = st["leads"], st["norm"]
        n_seq, n_static, n_out = st["dims"]
        for sd in st["members"]:
            net = _Net(n_seq, n_static, n_out, **st["hp"])
            net.load_state_dict(sd)
            net.eval()
            obj.members.append(net)
        return obj
